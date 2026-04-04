"""
Web Server V2 — Virtual Drug Discovery Lab
Updated imports to use V2 intelligent ranker
"""

import logging
import asyncio
from flask import Flask, render_template, request, jsonify
import sys
import os

# Fix encoding
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("virtual_drug_lab.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import V2 agents
from Agents.ranker_agent import rank_molecule_from_description
from Agents.printer_3d_agent import generate_3d_structure
from evaluators.ranker_evaluator import evaluate_ranker
from evaluators.printer_evaluator import evaluate_printer
from Agents.metrics import compute_pipeline_metrics

# Create Flask app
app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
app.config['JSON_SORT_KEYS'] = False

# ══���════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')


@app.route('/api/submit', methods=['POST'])
def submit_query():
    """Main API endpoint for pipeline processing"""
    try:
        data = request.get_json()
        query = data.get('description', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Description empty'
            }), 400
        
        logger.info(f"[WEB] Query received: {query[:100]}...")
        
        # Run async pipeline
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(_process_query(query))
            return jsonify({
                'success': True,
                'data': result
            })
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"[WEB] Error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)[:200]
        }), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Virtual Drug Lab V2 running'}), 200


# ═══════════════════════════════════════════════════════════════
# PIPELINE PROCESSOR
# ═══════════════════════════════════════════════════════════════

async def _process_query(description: str) -> dict:
    """Execute complete pipeline: Ranker → Printer → Metrics"""
    
    logger.info("[PIPELINE] 🚀 Starting pipeline V2...")
    
    # STAGE 1: RANKER V2
    logger.info("[PIPELINE] 1/3 Ranker V2 (intelligent classification)...")
    
    try:
        ranker_output = await rank_molecule_from_description(description)
    except Exception as e:
        logger.error(f"[RANKER] Error: {e}")
        raise Exception(f"Ranker failed: {str(e)[:100]}")
    
    ranker_metrics = evaluate_ranker(ranker_output)
    
    logger.info(
        f"[RANKER] ✅ Case {ranker_output.case}, "
        f"Confidence {ranker_output.confidence:.0%}, "
        f"Model {ranker_output.model}"
    )
    
    # STAGE 2: 3D PRINTER
    logger.info("[PIPELINE] 2/3 3D Printer...")
    
    try:
        v = ranker_output.input_validation
        smiles = v.get("smiles") if v.get("has_smiles") else None
        protein_seq = v.get("sequence_clean") if v.get("has_protein_sequence") else None
        mol_name = v.get("molecule_name", "Unknown")
        
        printer_output = await generate_3d_structure(
            ranker_output=ranker_output,
            smiles=smiles,
            protein_sequence=protein_seq,
            molecule_name=mol_name,
        )
    except Exception as e:
        logger.error(f"[PRINTER] Error: {e}")
        raise Exception(f"3D Printer failed: {str(e)[:100]}")
    
    printer_metrics = evaluate_printer(printer_output, case=ranker_output.case)
    
    logger.info(f"[PRINTER] ✅ Success={printer_output.success}, Format={printer_output.format}")
    
    # STAGE 3: METRICS
    logger.info("[PIPELINE] 3/3 Metrics aggregation...")
    
    pipeline_metrics = compute_pipeline_metrics(ranker_metrics, printer_metrics)
    
    # BUILD RESPONSE
    result = {
        'ranker': {
            'case': ranker_output.case,
            'model': ranker_output.model,
            'confidence': float(ranker_output.confidence),
            'llm_reasoning': ranker_output.llm_reasoning,
            'alternative_cases': ranker_output.alternative_cases or [],
            'validation': {
                'has_smiles': v.get('has_smiles', False),
                'has_protein_sequence': v.get('has_protein_sequence', False),
                'molecule_name': v.get('molecule_name', 'Unknown'),
                'smiles': v.get('smiles'),
                'sequence_length': v.get('sequence_length', 0),
                'mw': v.get('mw'),
                'logp': v.get('logp'),
                'drug_likeness': v.get('drug_likeness'),
            }
        },
        
        'printer': {
            'success': printer_output.success,
            'format': printer_output.format,
            'model_used': printer_output.model_used,
            'generation_time_s': float(printer_output.generation_time_s),
            'structure_size': len(printer_output.structure or ""),
            'error_message': printer_output.error_message,
            'structure': printer_output.structure,
        },
        
        'metrics': {
            'ranker': {
                'extraction': float(ranker_metrics.extraction_score),
                'classification': float(ranker_metrics.classification_score),
                'confidence': float(ranker_metrics.confidence_score),
                'reliability': float(ranker_metrics.reliability_score),
                'global': float(ranker_metrics.global_score),
                'status': ranker_metrics.status,
            },
            'printer': {
                'generation': float(printer_metrics.generation_score),
                'format': float(printer_metrics.format_score),
                'quality': float(printer_metrics.quality_score),
                'reliability': float(printer_metrics.reliability_score),
                'global': float(printer_metrics.global_score),
                'status': printer_metrics.status,
            },
            'pipeline': {
                'global': float(pipeline_metrics.pipeline_score),
                'status': pipeline_metrics.status,
            }
        }
    }
    
    logger.info("[PIPELINE] ✅ Complete!")
    return result


# ═══════════════════════════════════════════════════════════════
# SERVER STARTUP
# ═══════════════════════════════════════════════════════════════

def start_server(host='127.0.0.1', port=5000, debug=False):
    """Start Flask server"""
    logger.info(f"[SERVER] Starting on http://{host}:{port}")
    logger.info("[SERVER] Press CTRL+C to stop")
    
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == '__main__':
    start_server(debug=True)
# """
# Web Server — Virtual Drug Discovery Lab
# Serveur Flask pour interface web interactive
# Lance sur http://localhost:5000
# """

# import logging
# import asyncio
# from flask import Flask, render_template, request, jsonify
# from werkzeug.serving import run_simple
# import sys
# import os

# # Imports projet
# from Agents.ranker_agent import rank_molecule_from_description
# from Agents.printer_3d_agent import generate_3d_structure
# from evaluators.ranker_evaluator import evaluate_ranker
# from evaluators.printer_evaluator import evaluate_printer
# from Agents.metrics import compute_pipeline_metrics

# logger = logging.getLogger(__name__)

# # Créer l'app Flask
# app = Flask(__name__, 
#     template_folder='templates',
#     static_folder='static'
# )
# app.config['JSON_SORT_KEYS'] = False

# # ═══════════════════════════════════════════════════════════════
# # ROUTES
# # ═══════════════════════════════════════════════════════════════

# @app.route('/')
# def index():
#     """Page d'accueil - Saisie de la description"""
#     return render_template('index.html')


# @app.route('/api/submit', methods=['POST'])
# def submit_query():
#     """
#     Reçoit la description/query et lance le pipeline
    
#     Request JSON:
#     {
#         "description": "texte libre ou nom de molécule",
#         "query_type": "description" | "direct"  (optionnel)
#     }
#     """
#     try:
#         data = request.get_json()
#         query = data.get('description', '').strip()
        
#         if not query:
#             return jsonify({
#                 'success': False,
#                 'error': 'Description vide'
#             }), 400
        
#         logger.info(f"[WEB] Query reçue : {query[:100]}...")
        
#         # Lancer le pipeline asynchrone
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
        
#         try:
#             result = loop.run_until_complete(_process_query(query))
#             return jsonify({
#                 'success': True,
#                 'data': result
#             })
#         finally:
#             loop.close()
        
#     except Exception as e:
#         logger.error(f"[WEB] Erreur : {e}", exc_info=True)
#         return jsonify({
#             'success': False,
#             'error': str(e)[:200]
#         }), 500


# @app.route('/api/health', methods=['GET'])
# def health():
#     """Health check"""
#     return jsonify({'status': 'ok', 'message': 'Virtual Drug Lab is running'}), 200


# # ═══════════════════════════════════════════════════════════════
# # WORKER ASYNCHRONE
# # ═══════════════════════════════════════════════════════════════

# async def _process_query(description: str) -> dict:
#     """
#     Traite la query complète :
#     description → Ranker → Printer → Métriques
#     """
    
#     logger.info("[PIPELINE] Démarrage du pipeline...")
    
#     # ── ÉTAPE 1 : RANKER ────────────────────────────────────────
#     logger.info("[PIPELINE] 1/3 Ranker...")
    
#     try:
#         ranker_output = await rank_molecule_from_description(description)
#     except Exception as e:
#         logger.error(f"[RANKER] Erreur : {e}")
#         raise Exception(f"Ranker failed: {str(e)[:100]}")
    
#     # Évaluation Ranker
#     ranker_metrics = evaluate_ranker(ranker_output, extraction_method="llm")
    
#     logger.info(f"[RANKER] Case {ranker_output.case}, Confiance {ranker_output.confidence:.1%}")
    
#     # ── ÉTAPE 2 : 3D PRINTER ────────────────────────────────────
#     logger.info("[PIPELINE] 2/3 3D Printer...")
    
#     try:
#         v = ranker_output.input_validation
#         smiles = v.get("smiles") if v.get("has_smiles") else None
#         protein_seq = v.get("sequence_clean") if v.get("has_protein_sequence") else None
#         mol_name = v.get("molecule_name", "Unknown")
        
#         printer_output = await generate_3d_structure(
#             ranker_output=ranker_output,
#             smiles=smiles,
#             protein_sequence=protein_seq,
#             molecule_name=mol_name,
#         )
#     except Exception as e:
#         logger.error(f"[PRINTER] Erreur : {e}")
#         raise Exception(f"3D Printer failed: {str(e)[:100]}")
    
#     # Évaluation Printer
#     printer_metrics = evaluate_printer(printer_output, case=ranker_output.case)
    
#     logger.info(f"[PRINTER] Success {printer_output.success}, Format {printer_output.format}")
    
#     # ── ÉTAPE 3 : MÉTRIQUES ────────────────────────────────────
#     logger.info("[PIPELINE] 3/3 Métriques...")
    
#     pipeline_metrics = compute_pipeline_metrics(ranker_metrics, printer_metrics)
    
#     logger.info(f"[PIPELINE] Global Score {pipeline_metrics.pipeline_score:.1%}")
    
#     # ── RÉSULTAT FINAL ──────────────────────────────────────────
    
#     result = {
#         # Ranker
#         'ranker': {
#             'case': ranker_output.case,
#             'model': ranker_output.model,
#             'confidence': float(ranker_output.confidence),
#             'validation': {
#                 'has_smiles': v.get('has_smiles', False),
#                 'has_protein_sequence': v.get('has_protein_sequence', False),
#                 'molecule_name': v.get('molecule_name', 'Unknown'),
#                 'smiles': v.get('smiles'),
#                 'sequence_length': v.get('sequence_length', 0),
#                 'mw': v.get('mw'),
#                 'logp': v.get('logp'),
#                 'drug_likeness': v.get('drug_likeness'),
#                 'experiment_intent': v.get('experiment_intent'),
#             }
#         },
        
#         # Printer
#         'printer': {
#             'success': printer_output.success,
#             'format': printer_output.format,
#             'model_used': printer_output.model_used,
#             'generation_time_s': float(printer_output.generation_time_s),
#             'structure_size': len(printer_output.structure or ""),
#             'error_message': printer_output.error_message,
#             'structure': printer_output.structure,  # ← Pour affichage 3D
#         },
        
#         # Métriques
#         'metrics': {
#             'ranker': {
#                 'extraction': float(ranker_metrics.extraction_score),
#                 'classification': float(ranker_metrics.classification_score),
#                 'confidence': float(ranker_metrics.confidence_score),
#                 'reliability': float(ranker_metrics.reliability_score),
#                 'global': float(ranker_metrics.global_score),
#                 'status': ranker_metrics.status,
#             },
#             'printer': {
#                 'generation': float(printer_metrics.generation_score),
#                 'format': float(printer_metrics.format_score),
#                 'quality': float(printer_metrics.quality_score),
#                 'reliability': float(printer_metrics.reliability_score),
#                 'global': float(printer_metrics.global_score),
#                 'status': printer_metrics.status,
#             },
#             'pipeline': {
#                 'global': float(pipeline_metrics.pipeline_score),
#                 'status': pipeline_metrics.status,
#             }
#         }
#     }
    
#     logger.info("[PIPELINE] Terminé avec succès !")
#     return result


# # ═══════════════════════════════════════════════════════════════
# # DÉMARRAGE SERVEUR
# # ═══════════════════════════════════════════════════════════════

# def start_server(host='127.0.0.1', port=5000, debug=False):
#     """
#     Lance le serveur Flask
#     """
#     logger.info(f"[SERVER] Démarrage sur http://{host}:{port}")
#     logger.info("[SERVER] Appuyez sur CTRL+C pour arrêter")
    
#     app.run(
#         host=host,
#         port=port,
#         debug=debug,
#         use_reloader=False
#     )


# if __name__ == '__main__':
#     start_server(debug=True)