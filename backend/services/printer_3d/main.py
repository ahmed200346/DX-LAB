"""
Main Entry Point - Virtual Drug Discovery Lab V2
Intelligent LLM-based Classification
"""

import sys
import os
import logging

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("virtual_drug_lab_v2.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

from web_server import start_server

def main():
    """Launch server"""
    logger.info("="*70)
    logger.info("Virtual Drug Discovery Lab V2")
    logger.info("Intelligent LLM-based Classification + 3D Visualization")
    logger.info("="*70)
    logger.info("")
    logger.info("Starting server...")
    logger.info("Open http://localhost:5000 in your browser")
    logger.info("")
    logger.info("Press CTRL+C to stop")
    logger.info("="*70)
    
    start_server(host='127.0.0.1', port=5000, debug=False)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n✅ Server stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"[FATAL] {e}", exc_info=True)
        sys.exit(1)
# """
# Main — Virtual Drug Discovery Lab Web Server
# Lance un serveur local sur http://localhost:5000
# """

# import sys
# import os
# import logging

# # Fix encoding
# if sys.platform == "win32":
#     os.environ["PYTHONIOENCODING"] = "utf-8"

# # Logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler("virtual_drug_lab.log", encoding="utf-8"),
#         logging.StreamHandler(sys.stdout)
#     ]
# )

# logger = logging.getLogger(__name__)

# # Import serveur
# from web_server import start_server

# def main():
#     """Lance le serveur"""
#     logger.info("="*60)
#     logger.info("Virtual Drug Discovery Lab — Web Interface")
#     logger.info("="*60)
#     logger.info("")
#     logger.info("Serveur démarrant...")
#     logger.info("Ouvrez http://localhost:5000 dans votre navigateur")
#     logger.info("")
#     logger.info("Appuyez sur CTRL+C pour arrêter")
#     logger.info("="*60)
    
#     start_server(host='127.0.0.1', port=5000, debug=False)

# if __name__ == '__main__':
#     try:
#         main()
#     except KeyboardInterrupt:
#         logger.info("\nServeur arrêté")
#         sys.exit(0)
#     except Exception as e:
#         logger.error(f"[FATAL] {e}", exc_info=True)
#         sys.exit(1)
# #------Version stable------------------------
# """
# Main script — Virtual Drug Discovery Lab
# Pipeline : Description naturelle → Ranker → 3D Printer → Visualiseur

# Le Ranker DOIT déterminer le cas automatiquement depuis la description !
# """
# from evaluators.ranker_evaluator import evaluate_ranker, RankerMetrics
# from evaluators.printer_evaluator import evaluate_printer, PrinterMetrics
# from Agents.metrics import compute_pipeline_metrics, PipelineMetrics
# import sys
# import os
# import asyncio
# import logging
# import textwrap

# # ── Fix encodage Windows ────────────────────────────────────────
# if sys.platform == "win32":
#     os.environ["PYTHONIOENCODING"] = "utf-8"

# # ── Imports projet ──────────────────────────────────────────────
# from settings.configuration import MoleculeInput, LOGGING_CONFIG
# from Agents.ranker_agent import (
#     rank_molecule_from_description,
#     rank_molecule_from_structured,
# )
# from Agents.printer_3d_agent import generate_3d_structure
# from visualizer_3d import display_structure


# # ═══════════════════════════════════════════════════════════════
# # LOGGING
# # ═══════════════════════════════════════════════════════════════

# logging.basicConfig(
#     level=getattr(logging, LOGGING_CONFIG.get("level", "INFO")),
#     format=LOGGING_CONFIG.get("format", "%(asctime)s - %(levelname)s - %(message)s"),
#     handlers=[
#         logging.FileHandler(
#             LOGGING_CONFIG.get("log_file", "virtual_drug_lab.log"),
#             encoding="utf-8",
#         ),
#         logging.StreamHandler(sys.stdout),
#     ],
# )
# logger = logging.getLogger(__name__)


# # ═══════════════════════════════════════════════════════════════
# # DESCRIPTIONS DE TEST (SANS NUMÉROTATION!)
# # ═══════════════════════════════════════════════════════════════
# # Clés NEUTRES : le Ranker doit déterminer le cas automatiquement

# TEST_DESCRIPTIONS = {
#     # ── DESCRIPTION 1 : Petite molécule (RDKit) ────────────────
#     "molecule_aspirin": """
# Je travaille sur un projet de drug discovery pour le cancer. J'ai synthétisé 
# une nouvelle molécule prometteuse qui pourrait être un inhibiteur potentiel 
# de la tyrosine kinase EGFR (Epidermal Growth Factor Receptor).

# La structure chimique de ma molécule est relativement complexe. C'est un 
# composé hétérocyclique basé sur un scaffold de quinazoline. Voici son SMILES :
# CC(C)Nc1cc(nc2ccccc12)NC(=O)c3ccc(cc3)F

# Je l'ai nommée "EGFR-TK-Inhibitor-01" ou "ETI-001" pour faire court.

# Propriétés chimiques générales :
# - C'est une molécule organique de taille petite à moyenne
# - Elle contient un noyau aromatique bicyclique (quinazoline)
# - Une chaîne latérale avec un groupe carboxamide
# - Un atome de fluor (F) en position para du benzène

# Données expérimentales préliminaires :
# - Solubilité aqueuse : environ 50 μM (modérée)
# - pKa estimé : autour de 6.5
# - La molécule est lipophile mais pas excessivement (LogP ~ 2.5-3.0)
# - Masse moléculaire attendue : ~370-380 Da

# Objectif expérimental :
# Je veux générer la structure 3D complète de cette molécule pour analyser 
# la conformation optimale et évaluer les interactions potentielles.
# """,

#     # ── DESCRIPTION 2 : Protéine seule (ESMFold) ───────────────
#     "protein_ubiquitin": """
# Je travaille actuellement sur la protéine ubiquitine humaine dans le 
# contexte de mes recherches sur les mécanismes de dégradation cellulaire 
# et l'ubiquitination des protéines.

# La séquence d'acides aminés de la protéine ubiquitine humaine est :
# MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT

# L'ubiquitine est une petite protéine très bien conservée d'environ 76 acides 
# aminés. Elle joue un rôle crucial dans les processus cellulaires comme :
# - La régulation de la dégradation des protéines via le protéasome
# - La signalisation cellulaire
# - La réparation de l'ADN
# - L'autophagie

# J'ai besoin d'obtenir sa structure tridimensionnelle complète pour :
# 1. Analyser le repliement global et comprendre les domaines structuraux
# 2. Identifier les sites d'interaction avec d'autres protéines
# 3. Comparer avec les structures cristallographiques connues
# 4. Préparer des simulations de dynamique moléculaire

# C'est une protéine bien caractérisée, mais je voudrais une prédiction 
# de structure 3D moderne pour mon projet d'analyse comparative.
# """,

#     # ── DESCRIPTION 3 : Docking complexe (DiffDock) ─────────────
#     "docking_aspirin_cox2": """
# Je mène un projet de modélisation de docking pour comprendre comment 
# l'aspirine (acide acétylsalicylique) se lie à la cyclooxygénase-2 (COX-2), 
# son cible thérapeutique principale.

# La molécule ligand (aspirine) a le SMILES suivant :
# CC(=O)Oc1ccccc1C(=O)O

# Et la séquence de la protéine cible, la cyclooxygénase-2 humaine (COX-2), est :
# MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT

# L'aspirine est un analgésique et anti-inflammatoire bien connu qui inhibe 
# l'activité enzymatique de la COX-2 en acétylant une résine sérine critique 
# (Ser529) dans le site actif de l'enzyme.

# Mon objectif est de :
# 1. Générer une pose de docking réaliste de l'aspirine dans le site actif de la COX-2
# 2. Analyser les interactions ligand-protéine (liaisons hydrogène, contacts van der Waals)
# 3. Calculer l'affinité de liaison estimée
# 4. Comparer avec d'autres petits inhibiteurs de la COX-2
# 5. Comprendre le mécanisme d'acétylation au niveau structural

# J'ai besoin d'un modèle 3D du complexe aspirine-COX-2 avec une géométrie 
# optimisée pour la pose de docking, incluant les distances et orientations 
# des atomes importants.

# Contexte : L'aspirine est utilisée cliniquement depuis plus d'un siècle, 
# mais ses interactions structurales détaillées restent un domaine actif 
# de recherche.
# """,

#     # ── DESCRIPTION 4 : Cas ambigü / complexe (TEST du Ranker) ──
#     "test_ambiguous": """
# Bonjour, j'aimerais étudier comment la molécule CC(=O)Oc1ccccc1C(=O)O 
# (que j'appelle "Molécule X") interagit avec le site actif des protéines 
# du système immunitaire.

# J'ai une séquence protéique courte (ACDEFGHIKLMNPQRSTVWY) mais je ne sais pas 
# si c'est suffisant pour une prédiction.

# Pouvez-vous m'aider à générer une structure 3D? Je veux voir comment 
# ma molécule peut potentiellement se lier à des cibles biologiques.

# La molécule a les propriétés suivantes :
# - Masse : ~200-300 Da
# - LogP : entre 1 et 3
# - Présente plusieurs cycles aromatiques
# - Contient des groupes polaires

# S'il faut juste voir la structure de ma molécule seule, ça suffit aussi.
# S'il faut voir le docking avec la protéine, on peut faire ça.
# Je suis ouvert à toute suggestion !
# """,
# }

# # ═══════════════════════════════════════════════════════════════
# # COULEURS & AFFICHAGE
# # ═══════════════════════════════════════════════════════════════

# _USE_COLOR = sys.platform != "win32" or os.environ.get("COLORTERM")

# def _c(code: str, text: str) -> str:
#     return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

# BOLD    = lambda t: _c("1", t)
# GREEN   = lambda t: _c("32", t)
# YELLOW  = lambda t: _c("33", t)
# CYAN    = lambda t: _c("36", t)
# RED     = lambda t: _c("31", t)
# MAGENTA = lambda t: _c("35", t)
# DIM     = lambda t: _c("2", t)


# # ═══════════════════════════════════════════════════════════════
# # CORRESPONDANCES
# # ═══════════════════════════════════════════════════════════════

# _CASE_LABELS = {
#     1: ("Petite molécule",                "RDKit local",      "→ conformère 3D (.mol)"),
#     2: ("Protéine",                       "ESMFold NIM",      "→ structure 3D (.pdb)"),
#     3: ("Complexe ligand-protéine",       "DiffDock NIM",     "→ poses de docking (.pdb)"),
# }

# _MODEL_COLORS = {
#     "rdkit":        GREEN,
#     "esmfold_nim":  CYAN,
#     "diffdock_nim": MAGENTA,
# }


# # ═══════════════════════════════════════════════════════════════
# # FONCTIONS D'AFFICHAGE
# # ═══════════════════════════════════════════════════════════════

# def print_banner():
#     print()
#     print(BOLD("╔══════════════════════════════════════════════════════════╗"))
#     print(BOLD("║       Virtual Drug Discovery Lab  —  3D Pipeline        ║"))
#     print(BOLD("╚══════════════════════════════════════════════════════════╝"))
#     print()


# def print_separator(title: str = "", width: int = 70):
#     print()
#     print(BOLD("─" * width))
#     if title:
#         print(BOLD(f"  {title}"))
#         print(BOLD("─" * width))
#     print()


# def print_description(description: str):
#     print(DIM("  Description fournie :"))
#     for line in textwrap.wrap(description.strip(), width=66):
#         print(DIM(f"    {line}"))
#     print()


# def print_ranker_result(result) -> None:
#     """Affichage structuré du résultat Ranker."""
#     case   = result.case
#     label, model_label, output_label = _CASE_LABELS.get(case, ("?", "?", "?"))
#     color  = _MODEL_COLORS.get(result.model, YELLOW)

#     print(BOLD("  ┌─ RANKER ─────────────────────────────────────────────────"))
#     print(f"  │  Cas détecté    : {BOLD(str(case))} — {YELLOW(label)}")
#     print(f"  │  Modèle assigné : {color(result.model)}  {DIM(model_label)}")
#     print(f"  │  Confiance LLM  : {_confidence_bar(result.confidence)}")
#     print(BOLD("  │"))
#     print(BOLD("  │  Données extraites :"))

#     v = result.input_validation
#     _print_field(v, "molecule_name",     "  │    Nom")
#     _print_field(v, "experiment_intent", "  │    Intention")

#     if v.get("has_smiles"):
#         _print_field(v, "smiles",             "  │    SMILES")
#         _print_field(v, "mw",                 "  │    Masse molaire",  suffix=" Da")
#         _print_field(v, "logp",               "  │    LogP")
#         _print_field(v, "drug_likeness",      "  │    Drug-likeness")
#         _print_field(v, "complexity_note",    "  │    Complexité")
#         if v.get("is_peptide_smiles"):
#             print(f"  │    {YELLOW('⚠ Peptide détecté dans le SMILES')}")

#     if v.get("has_protein_sequence"):
#         _print_field(v, "sequence_note",      "  │    Séquence")
#         _print_field(v, "sequence_length",    "  │    Longueur",       suffix=" AA")

#     if v.get("smiles_error"):
#         print(f"  │    {RED('SMILES invalide : ' + str(v['smiles_error']))}")

#     print(BOLD("  └─────────────────────────────────────────────────────────"))
#     print()


# def print_printer_result(result, molecule_name: str = "Unknown") -> None:
#     """Affichage structuré du résultat 3D Printer."""
#     color = _MODEL_COLORS.get(result.model_used, YELLOW)

#     print(BOLD("  ┌─ 3D PRINTER ──────────────────────────────────────────────"))
#     print(f"  │  Modèle utilisé : {color(result.model_used)}")
#     print(f"  │  Format sortie  : {result.format.upper() if result.format else 'N/A'}")
#     print(f"  │  Temps          : {result.generation_time_s:.2f}s")
#     print(f"  │  Statut         : {GREEN('SUCCESS') if result.success else RED('ECHEC')}")

#     if result.error_message:
#         print(f"  │  {RED('Erreur : ' + str(result.error_message)[:120])}")

#     elif result.success and result.structure:
#         size_kb = len(result.structure) / 1024
#         print(f"  │  Taille fichier : {size_kb:.1f} Ko")
#         print(BOLD("  │"))
#         print(f"  │  {CYAN('Ouverture du visualiseur 3D dans le navigateur...')}")

#         try:
#             html_path = display_structure(
#                 result.structure,
#                 result.format,
#                 f"Case {result.case} — {molecule_name}",
#                 result.case,
#                 auto_open=True,
#             )
#             print(f"  │  Fichier HTML   : {DIM(html_path)}")
#         except Exception as e:
#             logger.error(f"[VISUALIZER] {e}")
#             print(f"  │  {YELLOW('Visualiseur indisponible : ' + str(e)[:80])}")

#     print(BOLD("  └─────────────────────────────────────────────────────────"))
#     print()


# def _print_field(d: dict, key: str, label: str, suffix: str = "") -> None:
#     val = d.get(key)
#     if val not in (None, "", False):
#         val_str = str(val)
#         if len(val_str) > 80:
#             val_str = val_str[:77] + "..."
#         print(f"{label:<28}: {val_str}{suffix}")


# def _confidence_bar(conf: float) -> str:
#     filled = int(conf * 10)
#     bar    = "█" * filled + "░" * (10 - filled)
#     pct    = f"{conf:.0%}"
#     if conf >= 0.80:
#         return GREEN(f"{bar} {pct}")
#     elif conf >= 0.65:
#         return YELLOW(f"{bar} {pct}")
#     else:
#         return RED(f"{bar} {pct} ⚠ faible")


# # ═══════════════════════════════════════════════════════════════
# # FONCTIONS DE TEST
# # ═══════════════════════════════════════════════════════════════
# async def run_full_pipeline(description: str, label: str = "") -> None:
#     """Pipeline complet avec métriques"""
    
#     print_separator(label or "PIPELINE COMPLET")
#     print_description(description)

#     # ── Étape 1 : Ranker ───────────────────────────────────────
#     print(BOLD("  [1/2] Ranker — analyse de la description..."))
    
#     try:
#         ranker_result = await rank_molecule_from_description(description)
#         print_ranker_result(ranker_result)
        
#         # ÉVALUATION RANKER
#         ranker_metrics = evaluate_ranker(ranker_result, extraction_method="llm")
#         print(str(ranker_metrics))
        
#     except Exception as e:
#         logger.error(f"[RANKER] {e}", exc_info=True)
#         print(f"\n  {RED('Ranker echoue :')} {str(e)[:200]}\n")
#         return

#     if not ranker_result or not ranker_result.case:
#         print(f"  {RED('Ranker : resultat invalide')}\n")
#         return

#     # ── Étape 2 : 3D Printer ───────────────────────────────────
#     print(BOLD("  [2/2] 3D Printer — génération de la structure..."))
    
#     try:
#         v = ranker_result.input_validation
#         smiles = v.get("smiles") if v.get("has_smiles") else None
#         protein_seq = v.get("sequence_clean") if v.get("has_protein_sequence") else None
#         mol_name = v.get("molecule_name", "Unknown")

#         printer_result = await generate_3d_structure(
#             ranker_output=ranker_result,
#             smiles=smiles,
#             protein_sequence=protein_seq,
#             molecule_name=mol_name,
#         )
#         print_printer_result(printer_result, mol_name)
        
#         # ÉVALUATION PRINTER
#         printer_metrics = evaluate_printer(printer_result, case=ranker_result.case)
#         print(str(printer_metrics))
        
#         # PIPELINE METRICS
#         pipeline_metrics = compute_pipeline_metrics(ranker_metrics, printer_metrics)
#         print(str(pipeline_metrics))

#     except Exception as e:
#         logger.error(f"[PRINTER] {e}", exc_info=True)
#         print(f"\n  {RED('3D Printer echoue :')} {str(e)[:200]}\n")
# # async def run_full_pipeline(description: str, label: str = "") -> None:
# #     """
# #     Exécute le pipeline complet depuis une description naturelle.
    
# #     LE RANKER DÉTERMINE AUTOMATIQUEMENT LE CAS !
# #     (Cas 1, 2 ou 3 selon le contenu)
# #     """
# #     print_separator(label or "PIPELINE COMPLET")
# #     print_description(description)

# #     # ── Étape 1 : Ranker ───────────────────────────────────────
# #     print(BOLD("  [1/2] Ranker — analyse de la description..."))
# #     print(DIM("         (Le Ranker détecte automatiquement le cas!)"))
    
# #     try:
# #         # ⭐ LE RANKER DÉCIDE AUTOMATIQUEMENT LE CAS ⭐
# #         ranker_result = await rank_molecule_from_description(description)
# #         print_ranker_result(ranker_result)
# #     except Exception as e:
# #         logger.error(f"[RANKER] {e}", exc_info=True)
# #         print(f"\n  {RED('Ranker echoue :')} {str(e)[:200]}\n")
# #         return

# #     if not ranker_result or not ranker_result.case:
# #         print(f"  {RED('Ranker : resultat invalide')}\n")
# #         return

# #     # ── Étape 2 : 3D Printer ───────────────────────────────────
# #     print(BOLD("  [2/2] 3D Printer — génération de la structure..."))
# #     try:
# #         v            = ranker_result.input_validation
# #         smiles       = v.get("smiles")       if v.get("has_smiles")           else None
# #         protein_seq  = v.get("sequence_clean") if v.get("has_protein_sequence") else None
# #         mol_name     = v.get("molecule_name", "Unknown")

# #         printer_result = await generate_3d_structure(
# #             ranker_output=ranker_result,
# #             smiles=smiles,
# #             protein_sequence=protein_seq,
# #             molecule_name=mol_name,
# #         )
# #         print_printer_result(printer_result, mol_name)

# #     except Exception as e:
# #         logger.error(f"[PRINTER] {e}", exc_info=True)
# #         print(f"\n  {RED('3D Printer echoue :')} {str(e)[:200]}\n")


# async def run_ranker_only(description: str, label: str = "") -> None:
#     """Exécute uniquement le Ranker (sans 3D Printer)."""
#     print_separator(label or "RANKER UNIQUEMENT")
#     print_description(description)

#     print(BOLD("  Ranker — analyse en cours..."))
#     print(DIM("  (Le Ranker détecte automatiquement le cas!)"))
    
#     try:
#         result = await rank_molecule_from_description(description)
#         print_ranker_result(result)
#     except Exception as e:
#         logger.error(f"[RANKER] {e}", exc_info=True)
#         print(f"\n  {RED('Erreur :')} {str(e)[:200]}\n")


# async def run_interactive() -> None:
#     """
#     Mode interactif : l'utilisateur saisit sa description en console.
#     Le Ranker détermine automatiquement le cas !
#     """
#     print_separator("MODE INTERACTIF")
#     print(DIM("  Décrivez votre molécule ou expérience en texte libre."))
#     print(DIM("  Le Ranker déterminera AUTOMATIQUEMENT s'il s'agit de :"))
#     print(DIM("    • CAS 1 : Petite molécule (SMILES seul)"))
#     print(DIM("    • CAS 2 : Protéine (séquence seule)"))
#     print(DIM("    • CAS 3 : Docking (SMILES + séquence)"))
#     print(DIM("  Tapez 'quit' ou 'exit' pour terminer.\n"))

#     while True:
#         try:
#             print(BOLD("  Votre description (Entrée 2× pour valider) :"))
#             lines = []
#             while True:
#                 line = input("  > ")
#                 if line.lower() in ("quit", "exit"):
#                     print(DIM("\n  Fin du mode interactif.\n"))
#                     return
#                 if line == "" and lines:
#                     break
#                 lines.append(line)

#             description = "\n".join(lines).strip()
#             if not description:
#                 print(YELLOW("  Description vide — reessayez.\n"))
#                 continue

#             await run_full_pipeline(description, "PIPELINE INTERACTIF")

#         except (KeyboardInterrupt, EOFError):
#             print(DIM("\n  Interrompu.\n"))
#             break


# async def run_all_examples() -> None:
#     """Exécute TOUS les exemples (sans pré-classification)."""
#     print_separator("TOUS LES EXEMPLES — LE RANKER DÉTECTE LE CAS")
    
#     examples = [
#         ("molecule_aspirin", "Exemple 1 : Inhibiteur EGFR (petite molécule)"),
#         ("protein_ubiquitin", "Exemple 2 : Protéine ubiquitine (structure seule)"),
#         ("docking_aspirin_cox2", "Exemple 3 : Docking aspirine-COX-2 (complexe)"),
#         ("test_ambiguous", "Exemple 4 : Cas ambigu (test Ranker)"),
#     ]
    
#     for key, label in examples:
#         description = TEST_DESCRIPTIONS.get(key, "")
#         if description:
#             await run_full_pipeline(description, label)
#             if key != "test_ambiguous":
#                 print(DIM("  Pause 2s avant l'exemple suivant...\n"))
#                 await asyncio.sleep(2)


# # ═══════════════════════════════════════════════════════════════
# # AIDE
# # ═══════════════════════════════════════════════════════════════

# HELP_TEXT = """
# Usage : python main.py [commande]

# Commandes disponibles :

#   EXAMPLES (Le Ranker détecte automatiquement le cas!) :
#     aspirin       → Inhibiteur EGFR (petite molécule → CAS 1)
#     ubiquitin     → Protéine ubiquitine (séquence → CAS 2)
#     docking       → Docking aspirine-COX-2 (complexe → CAS 3)
#     ambiguous     → Cas ambigu (test Ranker)
#     all           → Tous les exemples enchaînes

#   OTHER MODES :
#     interactive   → Saisie libre en console (Ranker détecte le cas)
#     structured    → Input structuré (bypass extraction LLM)

#   HELP :
#     help, -h, --help → Affiche cette aide

# IMPORTANT : Le Ranker DÉTERMINE AUTOMATIQUEMENT LE CAS depuis la description !
# Il ne faut PAS spécifier "case1", "case2" ou "case3" en input.

# Sans argument : exécute l'exemple "aspirin" (cas 1) par défaut.
# """


# # ═══════════════════════════════════════════════════════════════
# # POINT D'ENTRÉE
# # ═══════════════════════════════════════════════════════════════

# COMMANDS = {
#     "aspirin":     lambda: run_full_pipeline(TEST_DESCRIPTIONS["molecule_aspirin"], "Exemple 1 : Inhibiteur EGFR"),
#     "ubiquitin":   lambda: run_full_pipeline(TEST_DESCRIPTIONS["protein_ubiquitin"], "Exemple 2 : Protéine ubiquitine"),
#     "docking":     lambda: run_full_pipeline(TEST_DESCRIPTIONS["docking_aspirin_cox2"], "Exemple 3 : Docking aspirine-COX-2"),
#     "ambiguous":   lambda: run_full_pipeline(TEST_DESCRIPTIONS["test_ambiguous"], "Exemple 4 : Cas ambigu"),
#     "interactive": run_interactive,
#     "all":         run_all_examples,
# }


# async def main() -> None:
#     print_banner()

#     cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "aspirin"

#     if cmd in ("-h", "--help", "help"):
#         print(HELP_TEXT)
#         return

#     handler = COMMANDS.get(cmd)
#     if handler is None:
#         print(RED(f"  Commande inconnue : '{cmd}'"))
#         print(HELP_TEXT)
#         sys.exit(1)

#     await handler()
# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print(DIM("\n[INFO] Interrompu par l'utilisateur"))
#     except Exception as e:
#         logger.error(f"[FATAL] {e}", exc_info=True)
#         print(RED(f"\n[ERREUR FATALE] {e}"))
#         sys.exit(1)
#!!!!!!!!!!!!Version sans évaluation, pour tests rapides et démo !!!!!!!!!!!!
# """
# Main script — Virtual Drug Discovery Lab
# Pipeline : Description naturelle → Ranker → 3D Printer → Visualiseur

# Usage :
#     python main.py case1       → Petite molécule (RDKit)
#     python main.py case2       → Protéine (ESMFold NIM)
#     python main.py case3       → Docking moléculaire (DiffDock NIM)
#     python main.py case1r      → Ranker seul, cas 1
#     python main.py case2r      → Ranker seul, cas 2
#     python main.py case3r      → Ranker seul, cas 3
#     python main.py structured  → Input structuré (bypass LLM extraction)
#     python main.py interactive → Saisie libre en console
#     python main.py all         → Tous les cas enchaînés
# """

# import sys
# import os
# import asyncio
# import logging
# import textwrap
# from dataclasses import asdict

# # ── Fix encodage Windows ────────────────────────────────────────
# if sys.platform == "win32":
#     os.environ["PYTHONIOENCODING"] = "utf-8"

# # ── Imports projet ──────────────────────────────────────────────
# from settings.configuration import MoleculeInput, LOGGING_CONFIG
# from Agents.ranker_agent import (
#     rank_molecule_from_description,
#     rank_molecule_from_structured,
# )
# from Agents.printer_3d_agent import generate_3d_structure
# from visualizer_3d import display_structure


# # ═══════════════════════════════════════════════════════════════
# # LOGGING
# # ═══════════════════════════════════════════════════════════════

# logging.basicConfig(
#     level=getattr(logging, LOGGING_CONFIG.get("level", "INFO")),
#     format=LOGGING_CONFIG.get("format", "%(asctime)s - %(levelname)s - %(message)s"),
#     handlers=[
#         logging.FileHandler(
#             LOGGING_CONFIG.get("log_file", "virtual_drug_lab.log"),
#             encoding="utf-8",
#         ),
#         logging.StreamHandler(sys.stdout),
#     ],
# )
# logger = logging.getLogger(__name__)


# # ═══════════════════════════════════════════════════════════════
# # DESCRIPTIONS DE TEST
# # ═══════════════════════════════════════════════════════════════

# # Dans main.py, remplacez ou ajoutez dans TEST_DESCRIPTIONS :

# TEST_DESCRIPTIONS = {
#     "case_1": """
# Je travaille sur un projet de drug discovery pour le cancer. J'ai synthétisé 
# une nouvelle molécule prometteuse qui pourrait être un inhibiteur potentiel 
# de la tyrosine kinase EGFR (Epidermal Growth Factor Receptor).

# La structure chimique de ma molécule est relativement complexe. C'est un 
# composé hétérocyclique basé sur un scaffold de quinazoline. Voici son SMILES :
# CC(C)Nc1cc(nc2ccccc12)NC(=O)c3ccc(cc3)F

# Je l'ai nommée "EGFR-TK-Inhibitor-01" ou "ETI-001" pour faire court.

# Propriétés chimiques générales :
# - C'est une molécule organique de taille petite à moyenne
# - Elle contient un noyau aromatique bicyclique (quinazoline)
# - Il y a un groupe uracile-like (imidazole fusionné au benzène)
# - Une chaîne latérale avec un groupe carboxamide
# - Un atome de fluor (F) en position para du benzène

# Données expérimentales préliminaires :
# - Solubilité aqueuse : environ 50 μM (modérée)
# - pKa estimé : autour de 6.5 (peut être un acide faible)
# - La molécule est lipophile mais pas excessivement (LogP ~ 2.5-3.0)
# - En RMN ¹H, j'observe environ 15-20 protons
# - Masse moléculaire attendue : ~370-380 Da (petite molécule classique)

# Caractéristiques structurales importantes :
# - Le cycle quinazoline est le pharmacophore principal
# - Le groupe isopropyle (iPr = C(CH3)2H) en N1 augmente la lipophilicité
# - Le groupe carboxamide (-CO-NH-) est crucial pour la liaison H au récepteur
# - Le fluor en position para améliore la stabilité métabolique
# - La molécule respecte la règle de Lipinski (MW < 500, LogP < 5)

# Objectif expérimental :
# Je veux générer la structure 3D complète de cette molécule pour :
# 1. Analyser la conformation optimale
# 2. Prévoir les interactions avec EGFR via docking
# 3. Comparer les énergies conformationnelles
# 4. Évaluer si la géométrie matchée les hypothèses de binding

# Contexte scientifique :
# C'est un composé lead pour un projet pharma interne. Les quinazolines 
# sont bien connues comme inhibiteurs de tyrosine kinases. Mon composé 
# ajoute une modification originale avec ce groupe carboxamide para-fluoré.

# Je n'ai pas accès à un diffractomètre de rayons X pour déterminer la 
# structure cristallographique, donc j'ai besoin de générer les coordonnées 
# 3D par modélisation moléculaire.

# Merci de me donner une structure 3D optimisée de cette molécule !
# """,
# }
# TEST_DESCRIPTIONS2 = {
#     # ── CAS 1 : SMILES seul → RDKit ────────────────────────────
#     "case_1": """
# J'ai besoin de visualiser la structure 3D de l'aspirine (acide acétylsalicylique).
# Le SMILES est CC(=O)Oc1ccccc1C(=O)O.
# C'est un médicament anti-inflammatoire très courant.
# """,

#     # ── CAS 2 : Séquence seule → ESMFold NIM ───────────────────
#     "case_2": """
# Je travaille avec la protéine ubiquitine humaine.
# La séquence est : MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT
# Je dois obtenir sa structure 3D pour analyser le repliement protéique.
# """,

#     # ── CAS 3 : SMILES + séquence → DiffDock NIM ───────────────
#     "case_3": """
# Je dois étudier le docking moléculaire de l'aspirine (SMILES: CC(=O)Oc1ccccc1C(=O)O)
# sur la protéine COX-2 humaine.
# Séquence COX-2 : MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT
# Je veux voir comment la molécule s'insère dans le site actif.
# """,
# }

# Couleurs ANSI pour terminal (désactivées sur Windows si pas de support)
# _USE_COLOR = sys.platform != "win32" or os.environ.get("COLORTERM")

# def _c(code: str, text: str) -> str:
#     return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

# BOLD    = lambda t: _c("1", t)
# GREEN   = lambda t: _c("32", t)
# YELLOW  = lambda t: _c("33", t)
# CYAN    = lambda t: _c("36", t)
# RED     = lambda t: _c("31", t)
# MAGENTA = lambda t: _c("35", t)
# DIM     = lambda t: _c("2", t)


# # ═══════════════════════════════════════════════════════════════
# # AFFICHAGE
# # ═══════════════════════════════════════════════════════════════

# # Correspondances pour l'affichage
# _CASE_LABELS = {
#     1: ("Petite molécule",        "RDKit local",     "→ conformère 3D (.mol)"),
#     2: ("Protéine",               "ESMFold NIM",     "→ structure 3D (.pdb)"),
#     3: ("Complexe ligand-protéine","DiffDock NIM",   "→ poses de docking (.pdb)"),
# }
# _MODEL_COLORS = {
#     "rdkit":        GREEN,
#     "esmfold_nim":  CYAN,
#     "diffdock_nim": MAGENTA,
# }


# def print_banner():
#     print()
#     print(BOLD("╔══════════════════════════════════════════════════════════╗"))
#     print(BOLD("║       Virtual Drug Discovery Lab  —  3D Pipeline        ║"))
#     print(BOLD("╚══════════════════════════════════════════════════════════╝"))
#     print()


# def print_separator(title: str = "", width: int = 70):
#     print()
#     print(BOLD("─" * width))
#     if title:
#         print(BOLD(f"  {title}"))
#         print(BOLD("─" * width))
#     print()


# def print_description(description: str):
#     print(DIM("  Description fournie :"))
#     for line in textwrap.wrap(description.strip(), width=66):
#         print(DIM(f"    {line}"))
#     print()


# def print_ranker_result(result) -> None:
#     """Affichage structuré du résultat Ranker."""
#     case   = result.case
#     label, model_label, output_label = _CASE_LABELS.get(case, ("?", "?", "?"))
#     color  = _MODEL_COLORS.get(result.model, YELLOW)

#     print(BOLD("  ┌─ RANKER ─────────────────────────────────────────────────"))
#     print(f"  │  Cas classifié  : {BOLD(str(case))} — {YELLOW(label)}")
#     print(f"  │  Modèle assigné : {color(result.model)}  {DIM(model_label)}")
#     print(f"  │  Confiance LLM  : {_confidence_bar(result.confidence)}")
#     print(BOLD("  │"))
#     print(BOLD("  │  Données extraites :"))

#     v = result.input_validation
#     _print_field(v, "molecule_name",     "  │    Nom")
#     _print_field(v, "experiment_intent", "  │    Intention")

#     if v.get("has_smiles"):
#         _print_field(v, "smiles",             "  │    SMILES")
#         _print_field(v, "mw",                 "  │    Masse molaire",  suffix=" Da")
#         _print_field(v, "logp",               "  │    LogP")
#         _print_field(v, "drug_likeness",      "  │    Drug-likeness")
#         _print_field(v, "complexity_note",    "  │    Complexité")
#         if v.get("is_peptide_smiles"):
#             print(f"  │    {YELLOW('⚠ Peptide détecté dans le SMILES')}")

#     if v.get("has_protein_sequence"):
#         _print_field(v, "sequence_note",      "  │    Séquence")
#         _print_field(v, "sequence_length",    "  │    Longueur",       suffix=" AA")

#     if v.get("smiles_error"):
#         print(f"  │    {RED('SMILES invalide : ' + str(v['smiles_error']))}")

#     print(BOLD("  └─────────────────────────────────────────────────────────"))
#     print()


# def print_printer_result(result, molecule_name: str = "Unknown") -> None:
#     """Affichage structuré du résultat 3D Printer."""
#     color = _MODEL_COLORS.get(result.model_used, YELLOW)

#     print(BOLD("  ┌─ 3D PRINTER ──────────────────────────────────────────────"))
#     print(f"  │  Modèle utilisé : {color(result.model_used)}")
#     print(f"  │  Format sortie  : {result.format.upper() if result.format else 'N/A'}")
#     print(f"  │  Temps          : {result.generation_time_s:.2f}s")
#     print(f"  │  Statut         : {GREEN('SUCCESS') if result.success else RED('ÉCHEC')}")

#     if result.error_message:
#         print(f"  │  {RED('Erreur : ' + str(result.error_message)[:120])}")

#     elif result.success and result.structure:
#         size_kb = len(result.structure) / 1024
#         print(f"  │  Taille fichier : {size_kb:.1f} Ko")
#         print(BOLD("  │"))
#         print(f"  │  {CYAN('Ouverture du visualiseur 3D dans le navigateur...')}")

#         try:
#             html_path = display_structure(
#                 result.structure,
#                 result.format,
#                 f"Case {result.case} — {molecule_name}",
#                 result.case,
#                 auto_open=True,
#             )
#             print(f"  │  Fichier HTML   : {DIM(html_path)}")
#         except Exception as e:
#             logger.error(f"[VISUALIZER] {e}")
#             print(f"  │  {YELLOW('Visualiseur indisponible : ' + str(e)[:80])}")

#     print(BOLD("  └─────────────────────────────────────────────────────────"))
#     print()


# def _print_field(d: dict, key: str, label: str, suffix: str = "") -> None:
#     val = d.get(key)
#     if val not in (None, "", False):
#         val_str = str(val)
#         if len(val_str) > 80:
#             val_str = val_str[:77] + "..."
#         print(f"{label:<28}: {val_str}{suffix}")


# def _confidence_bar(conf: float) -> str:
#     filled = int(conf * 10)
#     bar    = "█" * filled + "░" * (10 - filled)
#     pct    = f"{conf:.0%}"
#     if conf >= 0.80:
#         return GREEN(f"{bar} {pct}")
#     elif conf >= 0.65:
#         return YELLOW(f"{bar} {pct}")
#     else:
#         return RED(f"{bar} {pct} ⚠ faible")


# # ═══════════════════════════════════════════════════════════════
# # FONCTIONS DE TEST
# # ═══════════════════════════════════════════════════════════════

# async def run_full_pipeline(description: str, label: str = "") -> None:
#     """
#     Exécute le pipeline complet depuis une description naturelle :
#     description → Ranker → 3D Printer → Visualiseur
#     """
#     print_separator(label or "PIPELINE COMPLET")
#     print_description(description)

#     # ── Étape 1 : Ranker ───────────────────────────────────────
#     print(BOLD("  [1/2] Ranker — analyse de la description..."))
#     try:
#         ranker_result = await rank_molecule_from_description(description)
#         print_ranker_result(ranker_result)
#     except Exception as e:
#         logger.error(f"[RANKER] {e}", exc_info=True)
#         print(f"\n  {RED('Ranker échoué :')} {str(e)[:200]}\n")
#         return

#     if not ranker_result or not ranker_result.case:
#         print(f"  {RED('Ranker : résultat invalide')}\n")
#         return

#     # ── Étape 2 : 3D Printer ───────────────────────────────────
#     print(BOLD("  [2/2] 3D Printer — génération de la structure..."))
#     try:
#         v            = ranker_result.input_validation
#         smiles       = v.get("smiles")       if v.get("has_smiles")           else None
#         protein_seq  = v.get("sequence_clean") if v.get("has_protein_sequence") else None
#         mol_name     = v.get("molecule_name", "Unknown")

#         printer_result = await generate_3d_structure(
#             ranker_output=ranker_result,
#             smiles=smiles,
#             protein_sequence=protein_seq,
#             molecule_name=mol_name,
#         )
#         print_printer_result(printer_result, mol_name)

#     except Exception as e:
#         logger.error(f"[PRINTER] {e}", exc_info=True)
#         print(f"\n  {RED('3D Printer échoué :')} {str(e)[:200]}\n")


# async def run_ranker_only(description: str, label: str = "") -> None:
#     """Exécute uniquement le Ranker (sans 3D Printer)."""
#     print_separator(label or "RANKER UNIQUEMENT")
#     print_description(description)

#     print(BOLD("  Ranker — analyse en cours..."))
#     try:
#         result = await rank_molecule_from_description(description)
#         print_ranker_result(result)
#     except Exception as e:
#         logger.error(f"[RANKER] {e}", exc_info=True)
#         print(f"\n  {RED('Erreur :')} {str(e)[:200]}\n")


# async def run_structured_input() -> None:
#     """
#     Test avec input structuré (bypass extraction LLM).
#     Modifiez les valeurs ci-dessous selon vos besoins.
#     """
#     print_separator("INPUT STRUCTURÉ — BYPASS LLM EXTRACTION")

#     # ── Exemples — décommentez le cas souhaité ──────────────────

#     mol = MoleculeInput(
#         smiles="CC(=O)Oc1ccccc1C(=O)O",
#         protein_sequence=None,
#         molecule_name="Aspirine (structuré)",
#     )

#     # mol = MoleculeInput(
#     #     smiles=None,
#     #     protein_sequence="MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAI",
#     #     molecule_name="Ubiquitine (structuré)",
#     # )

#     # mol = MoleculeInput(
#     #     smiles="CC(=O)Oc1ccccc1C(=O)O",
#     #     protein_sequence="MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAI",
#     #     molecule_name="Aspirine + COX-2 (docking structuré)",
#     # )

#     print(BOLD("  [1/2] Ranker — input structuré..."))
#     try:
#         ranker_result = await rank_molecule_from_structured(mol)
#         print_ranker_result(ranker_result)
#     except Exception as e:
#         logger.error(f"[RANKER] {e}", exc_info=True)
#         print(f"\n  {RED('Erreur :')} {str(e)[:200]}\n")
#         return

#     print(BOLD("  [2/2] 3D Printer..."))
#     try:
#         printer_result = await generate_3d_structure(
#             ranker_output=ranker_result,
#             smiles=mol.smiles,
#             protein_sequence=mol.protein_sequence,
#             molecule_name=mol.molecule_name,
#         )
#         print_printer_result(printer_result, mol.molecule_name)
#     except Exception as e:
#         logger.error(f"[PRINTER] {e}", exc_info=True)
#         print(f"\n  {RED('Erreur :')} {str(e)[:200]}\n")


# async def run_interactive() -> None:
#     """
#     Mode interactif : l'utilisateur saisit sa description en console.
#     Boucle jusqu'à 'quit' ou 'exit'.
#     """
#     print_separator("MODE INTERACTIF")
#     print(DIM("  Décrivez votre molécule ou expérience en texte libre."))
#     print(DIM("  Le pipeline extrait automatiquement SMILES, séquences, etc."))
#     print(DIM("  Tapez 'quit' ou 'exit' pour terminer.\n"))

#     while True:
#         try:
#             print(BOLD("  Votre description (Entrée 2× pour valider) :"))
#             lines = []
#             while True:
#                 line = input("  > ")
#                 if line.lower() in ("quit", "exit"):
#                     print(DIM("\n  Fin du mode interactif.\n"))
#                     return
#                 if line == "" and lines:
#                     break
#                 lines.append(line)

#             description = "\n".join(lines).strip()
#             if not description:
#                 print(YELLOW("  Description vide — réessayez.\n"))
#                 continue

#             await run_full_pipeline(description, "PIPELINE INTERACTIF")

#         except (KeyboardInterrupt, EOFError):
#             print(DIM("\n  Interrompu.\n"))
#             break


# async def run_all_cases() -> None:
#     """Exécute les 3 cas de test enchaînés."""
#     print_separator("TOUS LES CAS — PIPELINE COMPLET")
#     cases = [
#         ("case_1", "CAS 1 — Petite molécule (RDKit)"),
#         ("case_2", "CAS 2 — Protéine (ESMFold NIM)"),
#         ("case_3", "CAS 3 — Docking (DiffDock NIM)"),
#     ]
#     for key, label in cases:
#         await run_full_pipeline(TEST_DESCRIPTIONS[key], label)
#         if key != "case_3":
#             print(DIM("  Pause 2s entre les cas...\n"))
#             await asyncio.sleep(2)


# # ═══════════════════════════════════════════════════════════════
# # AIDE
# # ═══════════════════════════════════════════════════════════════

# HELP_TEXT = """
# Usage : python main.py [commande]

# Commandes disponibles :
#   case1         Pipeline complet — petite molécule (RDKit)
#   case2         Pipeline complet — protéine (ESMFold NIM)
#   case3         Pipeline complet — docking (DiffDock NIM)
#   case1r        Ranker seul — cas 1
#   case2r        Ranker seul — cas 2
#   case3r        Ranker seul — cas 3
#   structured    Input structuré (bypass extraction LLM)
#   interactive   Mode interactif — saisie libre en console
#   all           Tous les cas enchaînés

# Sans argument : exécute case1 par défaut.
# """


# # ═══════════════════════════════════════════════════════════════
# # POINT D'ENTRÉE
# # ═══════════════════════════════════════════════════════════════

# COMMANDS = {
#     "case1":       lambda: run_full_pipeline(TEST_DESCRIPTIONS["case_1"], "CAS 1 — Petite molécule (RDKit)"),
#     "case2":       lambda: run_full_pipeline(TEST_DESCRIPTIONS["case_2"], "CAS 2 — Protéine (ESMFold NIM)"),
#     "case3":       lambda: run_full_pipeline(TEST_DESCRIPTIONS["case_3"], "CAS 3 — Docking (DiffDock NIM)"),
#     "case1r":      lambda: run_ranker_only(TEST_DESCRIPTIONS["case_1"],   "CAS 1 — Ranker seul"),
#     "case2r":      lambda: run_ranker_only(TEST_DESCRIPTIONS["case_2"],   "CAS 2 — Ranker seul"),
#     "case3r":      lambda: run_ranker_only(TEST_DESCRIPTIONS["case_3"],   "CAS 3 — Ranker seul"),
#     "structured":  run_structured_input,
#     "interactive": run_interactive,
#     "all":         run_all_cases,
# }


# async def main() -> None:
#     print_banner()

#     cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "case1"

#     if cmd in ("-h", "--help", "help"):
#         print(HELP_TEXT)
#         return

#     handler = COMMANDS.get(cmd)
#     if handler is None:
#         print(RED(f"  Commande inconnue : '{cmd}'"))
#         print(HELP_TEXT)
#         sys.exit(1)

#     await handler()


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print(DIM("\n[INFO] Interrompu par l'utilisateur"))
#     except Exception as e:
#         logger.error(f"[FATAL] {e}", exc_info=True)
#         print(RED(f"\n[ERREUR FATALE] {e}"))
#         sys.exit(1)
