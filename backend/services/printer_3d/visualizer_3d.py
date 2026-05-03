"""
Enhanced 3D Visualizer with Chemical Properties
Affiche la structure 3D + propriétés chimiques extraites via RDKit
"""

import logging
from typing import Optional, Dict, Any
import tempfile
import webbrowser
import os
import json

logger = logging.getLogger(__name__)

# RDKit optional
try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors, AllChem
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
# PROPRIÉTÉS CHIMIQUES EXTRACTION
# ═══════════════════════════════════════════════════════════════

def extract_chemical_properties(structure_content: str, format_type: str, smiles: Optional[str] = None) -> Dict[str, Any]:
    """
    Extrait les propriétés chimiques de la structure
    Utilise RDKit si disponible + parsing manuel
    """
    
    properties = {
        "format": format_type,
        "has_rdkit": RDKIT_AVAILABLE,
        "properties": {}
    }
    
    # Si on a un SMILES, utiliser RDKit
    if smiles and RDKIT_AVAILABLE:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                mw = Descriptors.MolWt(mol)
                logp = Descriptors.MolLogP(mol)
                hbd = rdMolDescriptors.CalcNumHBD(mol)
                hba = rdMolDescriptors.CalcNumHBA(mol)
                rotatable_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)
                atoms = mol.GetNumAtoms()
                heavy_atoms = mol.GetNumHeavyAtoms()
                
                # Calcul Lipinski
                lipinski_violations = sum([
                    mw > 500,
                    logp > 5,
                    hbd > 5,
                    hba > 10
                ])
                
                properties["properties"] = {
                    "molecular_weight": round(mw, 2),
                    "logp": round(logp, 2),
                    "hbond_donors": hbd,
                    "hbond_acceptors": hba,
                    "rotatable_bonds": rotatable_bonds,
                    "total_atoms": atoms,
                    "heavy_atoms": heavy_atoms,
                    "lipinski_violations": lipinski_violations,
                    "drug_like": lipinski_violations <= 1,
                    "tpsa": round(Descriptors.TPSA(mol), 2),
                    "molar_refractivity": round(Descriptors.MolMR(mol), 2),
                }
                
                # Détection de groupes fonctionnels
                functional_groups = _detect_functional_groups(mol)
                if functional_groups:
                    properties["functional_groups"] = functional_groups
                
                logger.info(f"[VISUALIZER] Chemical properties extracted via RDKit")
                
        except Exception as e:
            logger.warning(f"[VISUALIZER] RDKit extraction failed: {e}")
    
    # Parsing manuel de la structure
    structure_info = _parse_structure_info(structure_content, format_type)
    if structure_info:
        properties["structure_info"] = structure_info
    
    return properties


def _detect_functional_groups(mol) -> Dict[str, int]:
    """Détecte les groupes fonctionnels courants"""
    
    if not RDKIT_AVAILABLE:
        return {}
    
    from rdkit.Chem import Lipinski, Crippen
    
    groups = {}
    
    # SMARTS patterns pour groupes courants
    patterns = {
        "carboxylic_acid": "[CX3](=O)[OX2H1]",
        "ester": "[#6][CX3](=O)[OX2H0]",
        "amide": "[NX3][CX3](=[OX1])[#6]",
        "alcohol": "[OX2H]",
        "amine": "[NX3;H2,H1;!$(NC=O)]",
        "ketone": "[#6][CX3](=O)[#6]",
        "aldehyde": "[CX3H1](=O)[#6]",
        "phenol": "[OX2H][cX3]:[c]",
        "thiol": "[SX2H]",
        "sulfide": "[#16X2H0]",
        "phosphate": "[PX4](=[OX1])([OX2H,OX1])([OX2H,OX1])",
    }
    
    for name, smarts in patterns.items():
        try:
            pattern = Chem.MolFromSmarts(smarts)
            if pattern:
                matches = mol.GetSubstructMatches(pattern)
                if matches:
                    groups[name] = len(matches)
        except:
            pass
    
    return groups


def _parse_structure_info(structure_content: str, format_type: str) -> Dict[str, Any]:
    """Parse les infos de la structure (PDB ou MOL)"""
    
    info = {}
    
    if format_type.lower() == "pdb":
        # Compter atomes, résidus
        atom_count = structure_content.count("ATOM") + structure_content.count("HETATM")
        residues = set()
        
        for line in structure_content.split("\n"):
            if line.startswith("ATOM") or line.startswith("HETATM"):
                try:
                    res_num = int(line[22:26])
                    residues.add(res_num)
                except:
                    pass
        
        info = {
            "atom_count": atom_count,
            "residue_count": len(residues),
            "type": "protein" if atom_count > 50 else "small_molecule"
        }
    
    elif format_type.lower() == "mol":
        # Compter atomes depuis header MOL
        lines = structure_content.split("\n")
        if len(lines) > 3:
            try:
                atom_count = int(lines[3].split()[0])
                info["atom_count"] = atom_count
                info["type"] = "small_molecule"
            except:
                pass
    
    return info


# ═══════════════════════════════════════════════════════════════
# HTML VIEWER AVEC PROPRIÉTÉS CHIMIQUES
# ═══════════════════════════════════════════════════════════════

def create_enhanced_html_viewer(
    structure_content: str,
    format_type: str,
    molecule_name: str,
    case: int,
    chemical_properties: Optional[Dict[str, Any]] = None,
    smiles: Optional[str] = None
) -> str:
    """
    Crée un viewer HTML enrichi avec:
    - Structure 3D interactive
    - Propriétés chimiques
    - Contrôles visualisation
    """
    
    # Extraire propriétés si non fournies
    if not chemical_properties:
        chemical_properties = extract_chemical_properties(structure_content, format_type, smiles)
    
    # Escape structure pour JS
    structure_escaped = structure_content.replace("'", "\\'").replace("\n", "\\n")
    
    # Case info
    case_info = {
        1: "Small Molecule (RDKit 3D Conformer)",
        2: "Protein Structure (ESMFold)",
        3: "Molecular Docking Complex (DiffDock)"
    }
    
    # Build properties HTML
    props_html = _build_properties_html(chemical_properties)
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D Drug Lab - {molecule_name}</title>
    <script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.2em;
            margin-bottom: 10px;
        }}
        
        .header p {{
            opacity: 0.9;
            font-size: 1em;
        }}
        
        .case-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            margin-top: 10px;
            font-weight: bold;
            font-size: 0.9em;
        }}
        
        .content {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            padding: 30px;
        }}
        
        .viewer-section {{
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        
        #viewer {{
            width: 100%;
            height: 600px;
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            position: relative;
        }}
        
        .controls {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        
        .controls button {{
            padding: 10px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s;
            flex: 1;
            min-width: 80px;
        }}
        
        .controls button:hover {{
            background: #764ba2;
            transform: translateY(-2px);
        }}
        
        .properties-section {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
            max-height: 700px;
            overflow-y: auto;
        }}
        
        .properties-section h3 {{
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.1em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .property-item {{
            background: white;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 3px solid #667eea;
        }}
        
        .property-label {{
            font-weight: bold;
            color: #333;
            font-size: 0.85em;
        }}
        
        .property-value {{
            color: #666;
            margin-top: 5px;
            font-size: 0.9em;
            font-family: 'Courier New', monospace;
        }}
        
        .property-status {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-top: 5px;
            font-weight: bold;
        }}
        
        .status-good {{
            background: #e8f5e9;
            color: #2e7d32;
        }}
        
        .status-warning {{
            background: #fff3e0;
            color: #e65100;
        }}
        
        .status-bad {{
            background: #ffebee;
            color: #c62828;
        }}
        
        .footer {{
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
            border-top: 1px solid #e0e0e0;
        }}
        
        @media (max-width: 1024px) {{
            .content {{
                grid-template-columns: 1fr;
            }}
            
            #viewer {{
                height: 400px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Virtual Drug Discovery Lab</h1>
            <p>3D Molecular Structure Visualization</p>
            <div class="case-badge">CASE {case}: {case_info.get(case, 'Unknown')}</div>
        </div>
        
        <div class="content">
            <div class="viewer-section">
                <div id="viewer" style="width:100%;"></div>
                
                <div class="controls">
                    <button onclick="setStyle('cartoon')">Cartoon</button>
                    <button onclick="setStyle('stick')">Stick</button>
                    <button onclick="setStyle('sphere')">Sphere</button>
                    <button onclick="setStyle('line')">Line</button>
                    <button onclick="resetView()">Reset</button>
                    <button onclick="toggleSpin()">Spin</button>
                </div>
            </div>
            
            <div class="properties-section">
                <h3>Chemical Properties</h3>
                <div class="property-item">
                    <div class="property-label">Name</div>
                    <div class="property-value">{molecule_name}</div>
                </div>
                
                {props_html}
            </div>
        </div>
        
        <div class="footer">
            Generated by Virtual Drug Discovery Lab | Powered by 3Dmol.js + RDKit
        </div>
    </div>
    
    <script>
        let viewer;
        let isSpinning = false;
        
        function initViewer() {{
            let element = document.getElementById('viewer');
            let config = {{ backgroundColor: 'white' }};
            viewer = $3Dmol.createViewer(element, config);
            
            let structure = `{structure_escaped}`;
            viewer.addModel(structure, "{format_type.upper()}");
            viewer.zoomTo();
            setStyle('stick');
            viewer.render();
        }}
        
        function setStyle(style) {{
            if (viewer) {{
                viewer.setStyle({{}}, {{}});
                
                if (style === 'cartoon') {{
                    viewer.setStyle({{}}, {{cartoon: {{color: 'spectrum'}}}});
                }} else if (style === 'stick') {{
                    viewer.setStyle({{}}, {{stick: {{colorscheme: 'Jmol'}}}});
                }} else if (style === 'sphere') {{
                    viewer.setStyle({{}}, {{sphere: {{}}}});
                }} else if (style === 'line') {{
                    viewer.setStyle({{}}, {{line: {{}}}});
                }}
                viewer.render();
            }}
        }}
        
        function resetView() {{
            if (viewer) {{
                viewer.zoomTo();
                viewer.render();
            }}
        }}
        
        function toggleSpin() {{
            if (viewer) {{
                isSpinning = !isSpinning;
                viewer.spin(isSpinning);
                viewer.render();
            }}
        }}
        
        window.addEventListener('load', initViewer);
    </script>
</body>
</html>
"""
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.html',
        delete=False,
        encoding='utf-8'
    ) as f:
        f.write(html_content)
        temp_path = f.name
    
    logger.info(f"[VISUALIZER] Enhanced HTML created: {temp_path}")
    return temp_path


def _build_properties_html(chem_props: Dict[str, Any]) -> str:
    """Construit le HTML des propriétés chimiques"""
    
    html = ""
    
    if not chem_props or "properties" not in chem_props:
        return '<div class="property-item">No chemical properties available</div>'
    
    props = chem_props["properties"]
    
    # Molecular Weight
    if "molecular_weight" in props:
        mw = props["molecular_weight"]
        mw_ok = 100 < mw < 900
        status_class = "status-good" if mw_ok else "status-warning"
        html += f"""
        <div class="property-item">
            <div class="property-label">Molecular Weight</div>
            <div class="property-value">{mw} Da
                <div class="property-status {status_class}">
                    {'✓ Drug-like' if mw_ok else '⚠ Out of range'}
                </div>
            </div>
        </div>
        """
    
    # LogP
    if "logp" in props:
        logp = props["logp"]
        logp_ok = -5 < logp < 5
        status_class = "status-good" if logp_ok else "status-warning"
        html += f"""
        <div class="property-item">
            <div class="property-label">LogP (Lipophilicity)</div>
            <div class="property-value">{logp}
                <div class="property-status {status_class}">
                    {'✓ Good' if logp_ok else '⚠ Caution'}
                </div>
            </div>
        </div>
        """
    
    # H-Bond Donors/Acceptors
    if "hbond_donors" in props:
        hbd = props["hbond_donors"]
        html += f"""
        <div class="property-item">
            <div class="property-label">H-Bond Donors</div>
            <div class="property-value">{hbd}</div>
        </div>
        """
    
    if "hbond_acceptors" in props:
        hba = props["hbond_acceptors"]
        html += f"""
        <div class="property-item">
            <div class="property-label">H-Bond Acceptors</div>
            <div class="property-value">{hba}</div>
        </div>
        """
    
    # Rotatable Bonds
    if "rotatable_bonds" in props:
        rb = props["rotatable_bonds"]
        html += f"""
        <div class="property-item">
            <div class="property-label">Rotatable Bonds</div>
            <div class="property-value">{rb}</div>
        </div>
        """
    
    # Atom Counts
    if "heavy_atoms" in props:
        ha = props["heavy_atoms"]
        html += f"""
        <div class="property-item">
            <div class="property-label">Heavy Atoms</div>
            <div class="property-value">{ha}</div>
        </div>
        """
    
    # TPSA
    if "tpsa" in props:
        tpsa = props["tpsa"]
        html += f"""
        <div class="property-item">
            <div class="property-label">TPSA</div>
            <div class="property-value">{tpsa} Ų</div>
        </div>
        """
    
    # Drug-Likeness
    if "drug_like" in props:
        is_drug_like = props["drug_like"]
        status = "✓ Drug-like" if is_drug_like else "⚠ Not drug-like"
        status_class = "status-good" if is_drug_like else "status-warning"
        html += f"""
        <div class="property-item">
            <div class="property-label">Drug-Likeness</div>
            <div class="property-value">
                <div class="property-status {status_class}">{status}</div>
            </div>
        </div>
        """
    
    # Functional Groups
    if "functional_groups" in chem_props and chem_props["functional_groups"]:
        groups = chem_props["functional_groups"]
        groups_str = ", ".join([f"{k}: {v}" for k, v in groups.items()])
        html += f"""
        <div class="property-item">
            <div class="property-label">Functional Groups</div>
            <div class="property-value">{groups_str}</div>
        </div>
        """
    
    # Structure Info
    if "structure_info" in chem_props:
        info = chem_props["structure_info"]
        if "atom_count" in info:
            html += f"""
            <div class="property-item">
                <div class="property-label">Atom Count</div>
                <div class="property-value">{info['atom_count']}</div>
            </div>
            """
        if "residue_count" in info:
            html += f"""
            <div class="property-item">
                <div class="property-label">Residue Count</div>
                <div class="property-value">{info['residue_count']}</div>
            </div>
            """
    
    return html if html else '<div class="property-item">Properties extracted via RDKit</div>'


def display_enhanced_structure(
    structure_content: str,
    format_type: str,
    molecule_name: str,
    case: int,
    smiles: Optional[str] = None,
    auto_open: bool = True
) -> str:
    """
    Affiche la structure avec propriétés
    """
    html_path = create_enhanced_html_viewer(
        structure_content,
        format_type,
        molecule_name,
        case,
        smiles=smiles
    )
    
    if auto_open:
        webbrowser.open('file://' + os.path.realpath(html_path))
        logger.info(f"[VISUALIZER] Opened in browser: {html_path}")
    
    return html_path
