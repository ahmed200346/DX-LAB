"""
Test Prompts V2 — Virtual Drug Discovery Lab
Comprehensive examples for testing intelligent LLM classification
Tests all 3 cases with multiple variations
"""

import asyncio
import json
from typing import Dict, List, Any

# Import your V2 ranker
from Agents.ranker_agent import rank_molecule_from_description

# ═══════════════════════════════════���═══════════════════════════
# TEST CASES CONFIGURATION
# ═══════════════════════════════════════════════════════════════

TEST_CASES: Dict[int, Dict[str, Any]] = {
    
    # ═══════════════════════════════════════════════════════════
    # CASE 1: SMALL MOLECULE (SMILES ONLY)
    # ═══════════════════════════════════════════════════════════
    
    1: {
        "name": "Small Molecule - SMILES Only",
        "expected_case": 1,
        "expected_model": "rdkit",
        "examples": [
            {
                "prompt": """I want to visualize the 3D structure of aspirin (acetylsalicylic acid). 
SMILES: CC(=O)Oc1ccccc1C(=O)O
It's a common anti-inflammatory drug used for pain relief.""",
                "description": "Aspirin - Direct SMILES with description",
                "difficulty": "Easy"
            },
            {
                "prompt": """Visualize caffeine molecule.
SMILES: CN1C=NC2=C1C(=O)N(C(=O)N2C)C""",
                "description": "Caffeine - SMILES only, no protein",
                "difficulty": "Easy"
            },
            {
                "prompt": """I need to analyze ibuprofen.
SMILES: CC(C)Cc1ccc(cc1)C(C)C(=O)O
This is an NSAID with MW around 206 Da.""",
                "description": "Ibuprofen - SMILES with chemical properties",
                "difficulty": "Easy"
            },
            {
                "prompt": """Generate 3D conformer for paracetamol (acetaminophen).
The SMILES is: CC(=O)Nc1ccc(O)cc1
It's a common painkiller and fever reducer.""",
                "description": "Paracetamol - SMILES with usage info",
                "difficulty": "Medium"
            },
            {
                "prompt": """Visualize nicotine molecule for structure analysis.
SMILES: CN1CCC[C@H]1c2cncnc2
Used in tobacco and some medications.""",
                "description": "Nicotine - Chiral SMILES",
                "difficulty": "Medium"
            },
            {
                "prompt": """I want to see the 3D structure of glucose.
SMILES: C([C@@H]1[C@H]([C@@H]([C@H](C(=O)O1)O)O)O)O
This is a simple sugar molecule.""",
                "description": "Glucose - Complex SMILES with stereo",
                "difficulty": "Hard"
            },
            {
                "prompt": """Analyze cholesterol structure.
SMILES: CC(C)CCCC(C)C1CCC2C1(CCCC2=CC=C3CC(CCC3=C)O)C
Important for understanding lipid metabolism.""",
                "description": "Cholesterol - Large SMILES",
                "difficulty": "Hard"
            },
            {
                "prompt": """Visualize aspirin only using SMILES: CC(=O)Oc1ccccc1C(=O)O
No protein sequence is needed.""",
                "description": "Aspirin - Minimal input (SMILES only)",
                "difficulty": "Easy"
            },
            {
                "prompt": """I have benzene ring: c1ccccc1
Can you generate its 3D structure?""",
                "description": "Benzene - Aromatic ring",
                "difficulty": "Easy"
            },
            {
                "prompt": """Dopamine molecule for neuroscience application:
SMILES: NCCc1ccc(O)c(O)c1""",
                "description": "Dopamine - Neurotransmitter",
                "difficulty": "Medium"
            }
        ]
    },
    
    # ═══════════════════════════════════════════════════════════
    # CASE 2: PROTEIN STRUCTURE (SEQUENCE ONLY)
    # ═══════════════════════════════════════════════════════════
    
    2: {
        "name": "Protein Structure - Sequence Only",
        "expected_case": 2,
        "expected_model": "esmfold_nim",
        "examples": [
            {
                "prompt": """I'm working with human ubiquitin protein for structural analysis.
Sequence: MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT
I need to predict its 3D structure using ESMFold.""",
                "description": "Ubiquitin - 76 amino acids",
                "difficulty": "Easy"
            },
            {
                "prompt": """Predict the structure of insulin chain A.
Sequence: GIVEQCCTSICSLYQLENYCN
This is a 21 amino acid peptide hormone.""",
                "description": "Insulin Chain A - Short peptide",
                "difficulty": "Easy"
            },
            {
                "prompt": """I want to study the 3D structure of myoglobin.
Amino acid sequence: GLSDGEWQQVLNVWGKVEADIAGHGQEVLIRLFTGHPETLEK
Myoglobin is an oxygen-binding protein in muscle tissue.""",
                "description": "Myoglobin - 43 amino acids",
                "difficulty": "Easy"
            },
            {
                "prompt": """Analyze Green Fluorescent Protein (GFP) chromophore region.
Sequence: MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVWWPTLVTTFSYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITHGMDELYK
This fluorescent protein is used in many biological applications.""",
                "description": "GFP - 238 amino acids",
                "difficulty": "Medium"
            },
            {
                "prompt": """Structure prediction for human hemoglobin subunit alpha.
Sequence: MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHG
KKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR
This is the alpha subunit of the oxygen transport protein.""",
                "description": "Hemoglobin alpha - 141 amino acids",
                "difficulty": "Hard"
            },
            {
                "prompt": """I need the 3D structure of lysozyme from egg white.
Protein sequence: MKALIVLVGTLVTQVA
SNHNAVDIKKASVPKGGFQAIVKEEALDGDGLVINNNVEYDISTGNLKLAMENIAIKHK
SALKASGVQNMDCAYGGIDSDLVMSDSGDIDSKGDYHEKDGKASFLVRVEYDTEKK
APWFLFCTQFGKKDA
Lysozyme is an antimicrobial enzyme with 129 amino acids.""",
                "description": "Lysozyme - 129 amino acids",
                "difficulty": "Hard"
            },
            {
                "prompt": """Protein structure analysis for p53 tumor suppressor (DNA-binding domain).
Sequence: SFSQYEQQ
ETGP GPGPGPGGG
CFFPCCGCCGCCCGCCGCCGCCGCCGCCGCCGCCCCCGCCGCCCCCGCCGCCGCCGCCGCCGCCGCCGCCGCCGC
This is the central DNA-binding domain of p53.""",
                "description": "p53 - 181 amino acids (partial)",
                "difficulty": "Hard"
            },
            {
                "prompt": """Predict 3D structure of angiotensin II.
Sequence: DRVYIHPF
This is a small bioactive peptide involved in blood pressure regulation.""",
                "description": "Angiotensin II - 8 amino acids (short)",
                "difficulty": "Medium"
            },
            {
                "prompt": """I want to visualize trypsin (digestive enzyme).
Sequence: IVGGYTCGANTVPYQFSYDPEKKSQKKSPLPSVFVPPSMIKEYAQKQTEVVAKCCYDDGKPCDIDCPFFPDAKK
This serine protease has 223 amino acids.""",
                "description": "Trypsin - 223 amino acids",
                "difficulty": "Hard"
            },
            {
                "prompt": """Structure prediction for oxytocin (love hormone).
Sequence: CYIQNCPLG
This is a 9 amino acid peptide hormone.""",
                "description": "Oxytocin - 9 amino acids",
                "difficulty": "Easy"
            }
        ]
    },
    
    # ═══════════════════════════════════════════════════════════
    # CASE 3: DOCKING COMPLEX (SMILES + SEQUENCE)
    # ═══════════════════════════════════════════════════════════
    
    3: {
        "name": "Docking Complex - SMILES + Protein",
        "expected_case": 3,
        "expected_model": "diffdock_nim",
        "examples": [
            {
                "prompt": """I need to study molecular docking of aspirin on COX-2 protein.
Ligand SMILES: CC(=O)Oc1ccccc1C(=O)O
Protein (COX-2) sequence: MNAYNLLNGPPQVACPQPVPKHHHHHHHHHHHHHSSHHHHVV
DLYDLDDQLAGLNSYGDLSVDNNYGFKVPASDSPPQIVKEQPFMQPPF
I want to see how the drug binds to the active site.""",
                "description": "Aspirin + COX-2 docking",
                "difficulty": "Easy"
            },
            {
                "prompt": """Predict docking of ibuprofen on its protein target.
Drug SMILES: CC(C)Cc1ccc(cc1)C(C)C(=O)O
Target protein sequence: MKVLWAALLVTAAGAKSSDQZPPPK
Ibuprofen is a common NSAID and I want to visualize binding.""",
                "description": "Ibuprofen + Target protein",
                "difficulty": "Medium"
            },
            {
                "prompt": """I want to study HIV protease inhibitor (ritonavir) docking.
Ligand SMILES: CC(C)c1ccc(cc1)CC(c2ccccc2)(c3ccc(cc3)C(C)C)C(=O)N4CCCC4C(=O)N(C)c5cccnc5
HIV Protease sequence: NFQ ZKPIVVEEV
SAEEVGINTQWKDSTCRQTPGWGSARYGEKVSPDYSVVFDQDLK
Ritonavir is an antiviral medication.""",
                "description": "Ritonavir + HIV Protease",
                "difficulty": "Hard"
            },
            {
                "prompt": """Molecular docking study: caffeine + adenosine receptor.
Caffeine SMILES: CN1C=NC2=C1C(=O)N(C(=O)N2C)C
Adenosine receptor 2A sequence: MNNSTTNSSS
TFQSQSQLYQNDSPQKRVRVQCQSGGGPVVQVHHHVLLLVVVVVVV
This will help understand caffeine's mechanism of action.""",
                "description": "Caffeine + Adenosine Receptor",
                "difficulty": "Medium"
            },
            {
                "prompt": """Docking analysis of methotrexate on dihydrofolate reductase (DHFR).
Methotrexate SMILES: CN(C)c1cc(ccc1N(C)C)C(=O)Nc2cc(ccc2Nc3nccc(c3)N4CCCC4)S(=O)(=O)N
DHFR sequence: MTIKEQNYSICGPLVISVAKVSSENLVKKVDLDVVLVSKNVGSDVEVTEKDVTKKKEVLVVNRDVDKIAQAHAKQHEVDLVVVKAAVVDRSSVKAGSEFMSRQ
Methotrexate is a cancer drug and antifolate agent.""",
                "description": "Methotrexate + DHFR",
                "difficulty": "Hard"
            },
            {
                "prompt": """Paracetamol docking on COX-1 enzyme.
Paracetamol SMILES: CC(=O)Nc1ccc(O)cc1
COX-1 sequence: MPPTTPVQHSLHGLPQMVFPQKVPPGGDDDDDGPPPPPPGP
PPPPPPPPPPPPPPPPPPPPPPPPPPPPPMPPPPPPPPPPPP
Analysis of how acetaminophen inhibits COX-1.""",
                "description": "Paracetamol + COX-1",
                "difficulty": "Medium"
            },
            {
                "prompt": """Study of clopidogrel (Plavix) docking on P2Y12 receptor.
Clopidogrel SMILES: COc1ccc(cc1)S(=O)(=O)N1CCCC1c2sc(cc2Cl)C(=O)O
P2Y12 receptor sequence: MGLLLRALGVVPPLLCFGSLSAYYVF
DKPPVVVFKDSQNGTYICEGPPHPPPFPPPPGQNGQR
Clopidogrel is an antiplatelet medication.""",
                "description": "Clopidogrel + P2Y12 Receptor",
                "difficulty": "Hard"
            },
            {
                "prompt": """Nicotine binding to acetylcholine receptor (AChR).
Nicotine SMILES: CN1CCC[C@H]1c2cncnc2
AChR sequence: MNNNGLAAENLF
FSVTMMCDPFDDYDDDDDDDADPPVVTKKVYSGQNLKIINQV
Nicotine agonist study for understanding addiction.""",
                "description": "Nicotine + AChR",
                "difficulty": "Medium"
            },
            {
                "prompt": """Docking study of aspirin (SMILES: CC(=O)Oc1ccccc1C(=O)O) with ubiquitin protein.
Ubiquitin: MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT
Unusual target for testing cross-reactivity.""",
                "description": "Aspirin + Ubiquitin (unusual)",
                "difficulty": "Hard"
            },
            {
                "prompt": """Dopamine docking on D2 dopamine receptor.
Dopamine SMILES: NCCc1ccc(O)c(O)c1
D2 receptor sequence: MVGNLQDSYYVYLYEAIMDLSPPPPPPPPPPPPV
VVVVVSVLLAVVVLVVLVPFFSLAYDELDGYKAPDP
Dopamine is a key neurotransmitter.""",
                "description": "Dopamine + D2 Receptor",
                "difficulty": "Medium"
            }
        ]
    }
}

# ═══════════════════════════════════════════════════════════════
# TEST RUNNER
# ═══════════════════════════════════════════════════════════════

async def test_single_prompt(prompt: str, expected_case: int) -> Dict[str, Any]:
    """Test a single prompt and return results"""
    
    try:
        result = await rank_molecule_from_description(prompt)
        
        is_correct = result.case == expected_case
        
        return {
            "success": True,
            "prompt_preview": prompt[:60] + "..." if len(prompt) > 60 else prompt,
            "expected_case": expected_case,
            "predicted_case": result.case,
            "model": result.model,
            "confidence": result.confidence,
            "correct": is_correct,
            "reasoning": result.llm_reasoning,
            "alternatives": result.alternative_cases,
            "validation": {
                "has_smiles": result.input_validation.get("has_smiles", False),
                "has_sequence": result.input_validation.get("has_protein_sequence", False),
                "molecule_name": result.input_validation.get("molecule_name", "Unknown"),
            }
        }
    
    except Exception as e:
        return {
            "success": False,
            "prompt_preview": prompt[:60] + "...",
            "expected_case": expected_case,
            "error": str(e),
            "error_type": type(e).__name__
        }


async def test_case(case_num: int, max_tests: int = None) -> Dict[str, Any]:
    """Test all examples for a specific case"""
    
    case_data = TEST_CASES[case_num]
    examples = case_data["examples"]
    
    if max_tests:
        examples = examples[:max_tests]
    
    print(f"\n{'='*80}")
    print(f"TESTING CASE {case_num}: {case_data['name'].upper()}")
    print(f"{'='*80}")
    print(f"Expected Model: {case_data['expected_model']}")
    print(f"Total Examples: {len(examples)}")
    print("")
    
    results = []
    correct_count = 0
    
    for i, example in enumerate(examples, 1):
        print(f"[{i}/{len(examples)}] Testing: {example['description']} ({example['difficulty']})")
        
        result = await test_single_prompt(
            example['prompt'],
            case_data['expected_case']
        )
        
        results.append(result)
        
        if result.get("success"):
            status = "✅ CORRECT" if result.get("correct") else "❌ WRONG"
            correct_count += result.get("correct", False)
            print(f"      {status} | Case: {result['predicted_case']} "
                  f"(Confidence: {result['confidence']:.0%}) | Model: {result['model']}")
            
            if result.get("reasoning"):
                print(f"      Reasoning: {result['reasoning'][:60]}...")
        else:
            print(f"      ❌ ERROR: {result.get('error', 'Unknown error')}")
        
        print("")
    
    accuracy = (correct_count / len(examples)) * 100 if examples else 0
    
    print(f"\n{'─'*80}")
    print(f"CASE {case_num} RESULTS:")
    print(f"  Correct: {correct_count}/{len(examples)} ({accuracy:.1f}%)")
    print(f"  Status: {'✅ PASSED' if accuracy >= 80 else '⚠️ NEEDS IMPROVEMENT' if accuracy >= 60 else '❌ FAILED'}")
    print(f"{'─'*80}\n")
    
    return {
        "case": case_num,
        "name": case_data["name"],
        "total_tests": len(examples),
        "correct": correct_count,
        "accuracy": accuracy,
        "results": results
    }


async def test_all_cases(max_per_case: int = None) -> None:
    """Test all cases"""
    
    print("\n")
    print("█" * 80)
    print("VIRTUAL DRUG DISCOVERY LAB V2")
    print("COMPREHENSIVE INTELLIGENT CLASSIFICATION TEST SUITE")
    print("█" * 80)
    
    all_results = []
    
    for case_num in [1, 2, 3]:
        case_result = await test_case(case_num, max_tests=max_per_case)
        all_results.append(case_result)
    
    # Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    total_correct = sum(r["correct"] for r in all_results)
    total_tests = sum(r["total_tests"] for r in all_results)
    overall_accuracy = (total_correct / total_tests * 100) if total_tests > 0 else 0
    
    for result in all_results:
        status = "✅" if result["accuracy"] >= 80 else "⚠️" if result["accuracy"] >= 60 else "❌"
        print(f"{status} Case {result['case']}: {result['accuracy']:.1f}% "
              f"({result['correct']}/{result['total_tests']})")
    
    print(f"\n{'─'*80}")
    print(f"OVERALL ACCURACY: {overall_accuracy:.1f}% ({total_correct}/{total_tests})")
    
    if overall_accuracy >= 90:
        print("🎉 EXCELLENT PERFORMANCE! V2 Classification is working great!")
    elif overall_accuracy >= 80:
        print("✅ GOOD PERFORMANCE! Minor improvements needed.")
    elif overall_accuracy >= 60:
        print("⚠️ FAIR PERFORMANCE. Tuning required.")
    else:
        print("❌ POOR PERFORMANCE. Review classification logic.")
    
    print("="*80 + "\n")
    
    return all_results


# ═══════════════════════════════════════════════════════════════
# QUICK TEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════

async def quick_test_case_1() -> None:
    """Quick test: Case 1 (Small Molecule)"""
    print("\n🧪 QUICK TEST: CASE 1 (Small Molecule)")
    await test_case(1, max_tests=3)


async def quick_test_case_2() -> None:
    """Quick test: Case 2 (Protein)"""
    print("\n🧪 QUICK TEST: CASE 2 (Protein)")
    await test_case(2, max_tests=3)


async def quick_test_case_3() -> None:
    """Quick test: Case 3 (Docking)"""
    print("\n🧪 QUICK TEST: CASE 3 (Docking)")
    await test_case(3, max_tests=3)


async def test_custom_prompt(prompt: str, expected_case: int) -> None:
    """Test a custom prompt"""
    print(f"\n🧪 CUSTOM TEST")
    print(f"Expected Case: {expected_case}")
    print(f"Prompt: {prompt[:100]}...")
    
    result = await test_single_prompt(prompt, expected_case)
    
    if result.get("success"):
        print(f"\n✅ Classification Result:")
        print(f"  Predicted Case: {result['predicted_case']}")
        print(f"  Model: {result['model']}")
        print(f"  Confidence: {result['confidence']:.0%}")
        print(f"  Correct: {'✅' if result['correct'] else '❌'}")
        print(f"  Reasoning: {result['reasoning']}")
        print(f"  SMILES Present: {result['validation']['has_smiles']}")
        print(f"  Sequence Present: {result['validation']['has_sequence']}")
    else:
        print(f"\n❌ Error: {result['error']}")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

async def main():
    """Main test runner"""
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "all":
            await test_all_cases()
        
        elif command == "quick":
            await quick_test_case_1()
            await quick_test_case_2()
            await quick_test_case_3()
        
        elif command.startswith("case"):
            case_num = int(command.replace("case", ""))
            max_tests = int(sys.argv[2]) if len(sys.argv) > 2 else None
            await test_case(case_num, max_tests=max_tests)
        
        elif command == "custom":
            if len(sys.argv) < 4:
                print("Usage: python test_prompts_v2.py custom '<prompt>' <case_number>")
                return
            prompt = sys.argv[2]
            case_num = int(sys.argv[3])
            await test_custom_prompt(prompt, case_num)
        
        else:
            print("Unknown command. Use: all, quick, case1, case2, case3, or custom")
    
    else:
        # Default: run all tests
        await test_all_cases()


if __name__ == "__main__":
    asyncio.run(main())