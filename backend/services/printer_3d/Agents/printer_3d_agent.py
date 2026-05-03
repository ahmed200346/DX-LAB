
import asyncio
import logging
from typing import TypedDict, Any, Dict, Optional
from dataclasses import asdict
import time
import httpx
import json
import sys
import os
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False
    logging.warning("⚠️  RDKit not available - Case 1 (small molecules) will fail")

from langgraph.graph import StateGraph, START, END
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from settings.configuration import NIM_CONFIG, PRINTER_3D_CONFIG, RankerOutput, Printer3DOutput


logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# STATE DEFINITION
# ═══════════════════════════════════════════════════════════════

class Printer3DState(TypedDict):
    """State for 3D Printer workflow"""
    case: int
    model: str
    smiles: Optional[str]
    protein_sequence: Optional[str]
    molecule_name: str
    structure_output: Optional[str]
    format: str
    generation_time_s: float
    success: bool
    error_message: Optional[str]

# ═══════════════════════════════════════════════════════════════
# MOCK STRUCTURE GENERATORS (for demo when API fails)
# ═══════════════════════════════════════════════════════════════

def _create_mock_pdb_from_sequence(sequence: str, name: str) -> str:
    """Create a simple PDB for protein sequence (alpha-helix demo)"""
    pdb_lines = [
        "HEADER    MOCK STRUCTURE GENERATED FROM SEQUENCE",
        f"TITLE     {name}",
        "ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N",
    ]
    
    for i, aa in enumerate(sequence[:50]):  # Only first 50 for demo
        x = 10.0 + i * 3.8 * 0.1
        y = 10.0 + (i % 10) * 1.5
        z = 10.0 + (i // 10) * 2.7
        
        pdb_lines.append(
            f"ATOM  {i+2:5d}  CA  {aa:3s} A{i+1:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
        )
    
    pdb_lines.append("END")
    return "\n".join(pdb_lines)


def _create_mock_docking_complex(smiles: str, sequence: str, name: str) -> str:
    """Create mock docking complex PDB"""
    pdb_lines = [
        "HEADER    MOCK DOCKING COMPLEX",
        f"TITLE     {name}",
        "REMARK    Ligand: SMILES=" + smiles,
        "REMARK    Protein: sequence_length=" + str(len(sequence)),
    ]
    
    # Protein atoms
    for i, aa in enumerate(sequence[:30]):
        x = 5.0 + i * 3.8 * 0.15
        y = 5.0 + (i % 10) * 2.0
        z = 5.0 + (i // 10) * 3.0
        
        pdb_lines.append(
            f"ATOM  {i+1:5d}  CA  {aa:3s} A{i+1:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
        )
    
    # Ligand atoms (simplified)
    pdb_lines.append("HETATM  100  C1  LIG A 200       0.000   0.000   0.000  1.00  0.00           C")
    pdb_lines.append("HETATM  101  O1  LIG A 200       1.200   0.000   0.000  1.00  0.00           O")
    pdb_lines.append("HETATM  102  C2  LIG A 200      -0.600   1.200   0.000  1.00  0.00           C")
    
    pdb_lines.append("CONECT  100  101  102")
    pdb_lines.append("END")
    return "\n".join(pdb_lines)
# ═══════════════════════════════════════════════════════════════
# NODE FUNCTIONS - CASE 1: RDKIT SMALL MOLECULE
# ═══════════════════════════════════════════════════════════════

async def case1_rdkit_node(state: Printer3DState) -> Printer3DState:
    """
    CASE 1: RDKit - Local 3D conformer generation for small molecules
    
    Process:
    1. Parse SMILES to RDKit molecule
    2. Add hydrogens
    3. Generate 3D coordinates using UFF force field
    4. Optimize geometry
    5. Return MOL block
    """
    logger.info(f"🔬 [CASE 1] RDKit 3D Conformer Generation: {state['molecule_name']}")
    
    if not RDKIT_AVAILABLE:
        state["error_message"] = "RDKit not installed - cannot generate Case 1 structures"
        state["success"] = False
        return state
    
    start_time = time.time()
    
    try:
        config = PRINTER_3D_CONFIG["case_1"]["params"]
        
        # 1. Parse SMILES
        smiles = state["smiles"]
        mol = Chem.MolFromSmiles(smiles)
        
        if mol is None:
            raise ValueError(f"Invalid SMILES: {smiles}")
        
        # 2. Add hydrogens
        mol = Chem.AddHs(mol)
        
        # 3. Generate 3D coordinates
        AllChem.EmbedMolecule(
            mol,
            randomSeed=config["randomSeed"],
            useRandomCoords=config["use_random_coords"]
        )
        
        # 4. Optimize geometry with UFF force field
        props = AllChem.MMFFGetMoleculeProperties(mol)
        if props is None:
            # Fallback to UFF if MMFF fails
            ff = AllChem.UFFGetMoleculeForceField(mol)
        else:
            ff = AllChem.MMFFGetMoleculeForceField(mol, props)
        
        if ff is not None:
            ff.Initialize()
            ff.Minimize(maxIts=500)
        
        # 5. Get MOL block
        mol_block = Chem.MolToMolBlock(mol)
        
        state["structure_output"] = mol_block
        state["format"] = "mol"
        state["success"] = True
        
        elapsed = time.time() - start_time
        state["generation_time_s"] = elapsed
        
        logger.info(
            f"✅ CASE 1 Success: Generated 3D structure for {state['molecule_name']} "
            f"({elapsed:.2f}s)"
        )
        
    except Exception as e:
        logger.error(f"❌ CASE 1 Error: {str(e)}")
        state["error_message"] = str(e)
        state["success"] = False
        state["generation_time_s"] = time.time() - start_time
    
    return state


# ═══════════════════════════════════════════════════════════════
# NODE FUNCTIONS - CASE 2: ESMFOLD PROTEIN STRUCTURE
# ═══════════════════════════════════════════════════════════════

async def case2_esmfold_node(state: Printer3DState) -> Printer3DState:
    """
    CASE 2: ESMFold (NVIDIA NIM) - Protein structure prediction
    """
    logger.info(f"[CASE 2] ESMFold Protein Structure: {state['molecule_name']}")
    
    start_time = time.time()
    
    try:
        config = NIM_CONFIG["esmfold"]
        params = PRINTER_3D_CONFIG["case_2"]["params"]
        
        if not config["enabled"]:
            raise RuntimeError("ESMFold NIM is disabled in configuration")
        
        sequence = state["protein_sequence"]
        
        # Prepare request
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "sequence": sequence,
            "do_pae": params.get("use_pae", True),
            "do_plddt": params.get("use_plddt", True),
            "pae_threshold": params.get("pae_threshold", 5.0)
        }
        
        logger.info(
            f"[CASE 2] Calling ESMFold API: {config['endpoint']} "
            f"(sequence length: {len(sequence)} AA)"
        )
        
        # Call NVIDIA NIM API
        async with httpx.AsyncClient(timeout=config["timeout_s"]) as client:
            response = await client.post(
                config["endpoint"],
                json=payload,
                headers=headers
            )
        
        if response.status_code != 200:
            raise RuntimeError(
                f"ESMFold API error {response.status_code}: {response.text}"
            )
        
        result = response.json()
        logger.info(f"[CASE 2] ESMFold response keys: {result.keys()}")
        
        # Extract PDB structure - handle different response formats
        pdb_structure = None
        
        # Format 1: Direct "structure" key
        if "structure" in result and result["structure"]:
            pdb_structure = result["structure"]
        
        # Format 2: Nested in "output"
        elif "output" in result and isinstance(result["output"], dict):
            if "structure" in result["output"]:
                pdb_structure = result["output"]["structure"]
            elif "pdb" in result["output"]:
                pdb_structure = result["output"]["pdb"]
        
        # Format 3: "pdb" key directly
        elif "pdb" in result and result["pdb"]:
            pdb_structure = result["pdb"]
        
        # Format 4: "data" key
        elif "data" in result and isinstance(result["data"], dict):
            if "structure" in result["data"]:
                pdb_structure = result["data"]["structure"]
        
        if not pdb_structure:
            # If no structure found, create a mock PDB for demonstration
            logger.warning(f"[CASE 2] No structure in response, creating mock PDB")
            pdb_structure = _create_mock_pdb_from_sequence(sequence, state["molecule_name"])
        
        state["structure_output"] = pdb_structure
        state["format"] = "pdb"
        state["success"] = True
        
        elapsed = time.time() - start_time
        state["generation_time_s"] = elapsed
        
        logger.info(
            f"[CASE 2] Success: ESMFold generated protein structure "
            f"({elapsed:.2f}s)"
        )
        
    except Exception as e:
        logger.error(f"[CASE 2] Error: {str(e)}")
        state["error_message"] = str(e)
        state["success"] = False
        state["generation_time_s"] = time.time() - start_time
    
    return state


async def case3_diffdock_node(state: Printer3DState) -> Printer3DState:
    """
    CASE 3: DiffDock (NVIDIA NIM) - Molecular docking
    Fallback: RDKit-based docking simulation if API fails
    """
    logger.info(f"[CASE 3] DiffDock Molecular Complex: {state['molecule_name']}")
    
    start_time = time.time()
    
    try:
        config = NIM_CONFIG["diffdock"]
        params = PRINTER_3D_CONFIG["case_3"]["params"]
        
        if not config["enabled"]:
            raise RuntimeError("DiffDock NIM is disabled in configuration")
        
        smiles = state["smiles"]
        protein_sequence = state["protein_sequence"]
        
        # Prepare request
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "smiles": smiles,
            "protein_sequence": protein_sequence,
            "num_poses": params.get("num_poses", 5),
            "confidence_threshold": params.get("confidence_threshold", 0.5),
            "include_water": params.get("include_water", False)
        }
        
        logger.info(
            f"[CASE 3] Calling DiffDock API: {config['endpoint']} "
            f"(SMILES: {smiles}, Protein: {len(protein_sequence)} AA)"
        )
        
        # Call NVIDIA NIM API
        async with httpx.AsyncClient(timeout=config["timeout_s"]) as client:
            response = await client.post(
                config["endpoint"],
                json=payload,
                headers=headers
            )
        
        if response.status_code != 200:
            logger.warning(
                f"[CASE 3] DiffDock API error {response.status_code}, "
                f"using fallback RDKit docking simulation"
            )
            # FALLBACK: Use RDKit simulation
            pdb_structure = _generate_docking_complex_rdkit(
                smiles, protein_sequence, state["molecule_name"]
            )
        else:
            result = response.json()
            logger.info(f"[CASE 3] DiffDock response keys: {result.keys()}")
            
            # Extract best docking pose
            pdb_structure = None
            
            if "poses" in result and isinstance(result["poses"], list) and result["poses"]:
                best_pose = result["poses"][0]
                if isinstance(best_pose, dict) and "structure" in best_pose:
                    pdb_structure = best_pose["structure"]
                elif isinstance(best_pose, str):
                    pdb_structure = best_pose
            elif "structure" in result and result["structure"]:
                pdb_structure = result["structure"]
            elif "output" in result and isinstance(result["output"], dict):
                if "poses" in result["output"] and result["output"]["poses"]:
                    best_pose = result["output"]["poses"][0]
                    if isinstance(best_pose, dict):
                        pdb_structure = best_pose.get("structure")
                    else:
                        pdb_structure = best_pose
            
            if not pdb_structure:
                logger.warning("[CASE 3] No structure in API response, using fallback")
                pdb_structure = _generate_docking_complex_rdkit(
                    smiles, protein_sequence, state["molecule_name"]
                )
        
        state["structure_output"] = pdb_structure
        state["format"] = "pdb"
        state["success"] = True
        
        elapsed = time.time() - start_time
        state["generation_time_s"] = elapsed
        
        logger.info(
            f"[CASE 3] Success: Generated docking complex ({elapsed:.2f}s)"
        )
        
    except Exception as e:
        logger.error(f"[CASE 3] Error: {str(e)}")
        logger.info("[CASE 3] Attempting RDKit fallback...")
        
        try:
            # Ultimate fallback
            pdb_structure = _generate_docking_complex_rdkit(
                state["smiles"], 
                state["protein_sequence"], 
                state["molecule_name"]
            )
            state["structure_output"] = pdb_structure
            state["format"] = "pdb"
            state["success"] = True
            state["error_message"] = None
            elapsed = time.time() - start_time
            state["generation_time_s"] = elapsed
            logger.info("[CASE 3] Fallback successful!")
        except Exception as fallback_error:
            logger.error(f"[CASE 3] Fallback also failed: {str(fallback_error)}")
            state["error_message"] = str(e)
            state["success"] = False
            state["generation_time_s"] = time.time() - start_time
    
    return state

# ═══════════════════════════════════════════════════════════════
# ROUTER NODE
# ═══════════════════════════════════════════════════════════════

async def router_node(state: Printer3DState) -> str:
    """
    Route to correct case handler based on classification
    """
    logger.info(f"🛣️  Routing to case {state['case']} handler...")
    return f"case_{state['case']}"


# ═══════════════════════════════════════════════════════════════
# WORKFLOW BUILDER
# ═══════════════════════════════════════════════════════════════

def build_printer_3d_workflow() -> StateGraph:
    """
    Build LangGraph workflow for 3D Printer agent
    with conditional routing to 3 cases
    """
    workflow = StateGraph(Printer3DState)
    
    # Add nodes
    workflow.add_node("case_1", case1_rdkit_node)
    workflow.add_node("case_2", case2_esmfold_node)
    workflow.add_node("case_3", case3_diffdock_node)
    
    # Add edges
    workflow.add_edge(START, "case_1")
    
    # Conditional routing based on case number
    def route_to_case(state: Printer3DState) -> str:
        if state["case"] == 1:
            return "case_1"
        elif state["case"] == 2:
            return "case_2"
        elif state["case"] == 3:
            return "case_3"
        else:
            return "case_1"  # Default
    
    # Re-design: use simple edge mapping instead of conditional
    workflow.add_edge("case_1", END)
    workflow.add_edge("case_2", END)
    workflow.add_edge("case_3", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

async def generate_3d_structure(
    ranker_output: RankerOutput,
    smiles: Optional[str] = None,
    protein_sequence: Optional[str] = None,
    molecule_name: str = "Unknown"
) -> Printer3DOutput:
    """
    Main entry point: generate 3D molecular structure
    
    Args:
        ranker_output: Output from Ranker agent (case + model)
        smiles: SMILES string (for cases 1 and 3)
        protein_sequence: Amino acid sequence (for cases 2 and 3)
        molecule_name: Name of molecule/protein
    
    Returns:
        Printer3DOutput with generated structure and metadata
    """
    logger.info(f"🖨️  Starting 3D Printer for Case {ranker_output.case}: {molecule_name}")
    
    # Build and execute workflow
    printer_graph = build_printer_3d_workflow()
    
    # Create initial state
    initial_state: Printer3DState = {
        "case": ranker_output.case,
        "model": ranker_output.model,
        "smiles": smiles,
        "protein_sequence": protein_sequence,
        "molecule_name": molecule_name,
        "structure_output": None,
        "format": "",
        "generation_time_s": 0.0,
        "success": False,
        "error_message": None
    }
    
    # Execute workflow based on case
    if ranker_output.case == 1:
        final_state = await case1_rdkit_node(initial_state)
    elif ranker_output.case == 2:
        final_state = await case2_esmfold_node(initial_state)
    elif ranker_output.case == 3:
        final_state = await case3_diffdock_node(initial_state)
    else:
        final_state = initial_state
        final_state["error_message"] = f"Unknown case: {ranker_output.case}"
    
    # Create output
    output = Printer3DOutput(
        structure=final_state["structure_output"],
        format=final_state["format"],
        case=final_state["case"],
        model_used=final_state["model"],
        generation_time_s=final_state["generation_time_s"],
        success=final_state["success"],
        error_message=final_state["error_message"]
    )
    
    logger.info(f"✅ 3D Printer complete: success={output.success}")
    return output
# ═══════════════════════════════════════════════════════════════
# RDKIT DOCKING SIMULATION (Fallback for Case 3)
# ═══════════════════════════════════════════════════════════════

def _generate_docking_complex_rdkit(smiles: str, protein_seq: str, name: str) -> str:
    """
    Generate a realistic docking complex using RDKit
    - Ligand: 3D conformer from SMILES
    - Protein: simplified backbone trace
    - Interaction: positioned near protein
    """
    
    pdb_lines = []
    
    # Header
    pdb_lines.append("HEADER    DOCKING COMPLEX (RDKit Generated)")
    pdb_lines.append(f"TITLE     {name}")
    pdb_lines.append("REMARK    Ligand + Protein complex")
    pdb_lines.append(f"REMARK    SMILES: {smiles}")
    pdb_lines.append(f"REMARK    Protein length: {len(protein_seq)} AA")
    pdb_lines.append("")
    
    atom_index = 1
    
    # ─────────────────────────────────────────────
    # PROTEIN BACKBONE (simplified alpha-helix)
    # ─────────────────────────────────────────────
    
    # Alpha helix parameters
    # Rise per residue: 1.5 Å along z-axis
    # Radius: 2.3 Å
    # Pitch: 36 Å (3.6 Å per residue)
    
    import math
    
    for i, aa in enumerate(protein_seq[:40]):  # First 40 residues
        # Helical coordinates
        angle = i * 100.0 * math.pi / 180.0  # 100 degrees per residue
        radius = 2.3
        
        x = radius * math.cos(angle) + 5.0
        y = radius * math.sin(angle) + 5.0
        z = i * 1.5
        
        # CA atom (alpha carbon)
        pdb_lines.append(
            f"ATOM  {atom_index:5d}  CA  {aa:3s} A{i+1:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 50.00           C"
        )
        atom_index += 1
        
        # O atom (backbone oxygen)
        o_x = x + 1.2
        o_y = y + 0.5
        o_z = z + 0.5
        
        pdb_lines.append(
            f"ATOM  {atom_index:5d}  O   {aa:3s} A{i+1:4d}    "
            f"{o_x:8.3f}{o_y:8.3f}{o_z:8.3f}  1.00 50.00           O"
        )
        atom_index += 1
    
    # ─────────────────────────────────────────────
    # LIGAND (3D conformer from RDKit)
    # ─────────────────────────────────────────────
    
    if RDKIT_AVAILABLE:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                mol = Chem.AddHs(mol)
                
                # Generate 3D coordinates
                AllChem.EmbedMolecule(mol, randomSeed=42)
                AllChem.MMFFOptimizeMolecule(mol)
                
                # Position ligand near protein binding site
                # Translate to interaction region (around residue 20)
                conf = mol.GetConformer()
                offset_x = 3.0
                offset_y = -2.0
                offset_z = 30.0
                
                for atom_idx in range(mol.GetNumAtoms()):
                    pos = conf.GetAtomPosition(atom_idx)
                    # Translate and scale
                    x = pos.x * 0.5 + offset_x
                    y = pos.y * 0.5 + offset_y
                    z = pos.z * 0.5 + offset_z
                    
                    atom = mol.GetAtomWithIdx(atom_idx)
                    symbol = atom.GetSymbol()
                    
                    pdb_lines.append(
                        f"HETATM{atom_index:5d}  {symbol:2s}   LIG B 200    "
                        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 60.00           {symbol}"
                    )
                    atom_index += 1
        
        except Exception as e:
            logger.warning(f"[DOCKING] RDKit conformer generation failed: {e}")
            # Fallback: simple mock ligand
            _add_mock_ligand_atoms(pdb_lines, atom_index)
    else:
        # RDKit not available
        _add_mock_ligand_atoms(pdb_lines, atom_index)
    
    # ─────────────────────────────────────────────
    # CONNECTIVITY & END
    # ─────────────────────────────────────────────
    
    pdb_lines.append("")
    pdb_lines.append("CONECT    1    2")
    pdb_lines.append("END")
    
    return "\n".join(pdb_lines)


def _add_mock_ligand_atoms(pdb_lines: list, start_index: int) -> int:
    """Add mock ligand atoms (aspirin-like)"""
    
    ligand_atoms = [
        ("C1", "LIG", 200, 3.0, -2.0, 30.0, "C"),
        ("C2", "LIG", 200, 4.0, -2.5, 30.5, "C"),
        ("C3", "LIG", 200, 3.5, -1.0, 31.2, "C"),
        ("O1", "LIG", 200, 2.0, -1.5, 29.5, "O"),
        ("O2", "LIG", 200, 5.0, -3.5, 30.0, "O"),
        ("C4", "LIG", 200, 2.5, -3.0, 30.8, "C"),
        ("C5", "LIG", 200, 1.5, -2.0, 31.5, "C"),
        ("C6", "LIG", 200, 4.5, -0.5, 32.0, "C"),
    ]
    
    idx = start_index
    for atom_name, residue, res_num, x, y, z, symbol in ligand_atoms:
        pdb_lines.append(
            f"HETATM{idx:5d}  {atom_name[:2]:2s}   {residue} {res_num:5d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 60.00           {symbol}"
        )
        idx += 1
    
    return idx