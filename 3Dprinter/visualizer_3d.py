"""
3D Structure Visualizer
Supports MOL, PDB formats with py3Dmol
"""

import logging
from typing import Optional
import tempfile
import subprocess
import webbrowser
import os

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# INSTALL PY3DMOL
# ═══════════════════════════════════════════════════════════════

def ensure_py3dmol():
    """Ensure py3Dmol is installed"""
    try:
        import py3Dmol
    except ImportError:
        logger.warning("[VISUALIZER] Installing py3Dmol...")
        subprocess.check_call([
            "pip", "install", "py3Dmol", "-q"
        ])


# ═══════════════════════════════════════════════════════════════
# HTML VISUALIZATION
# ═══════════════════════════════════════════════════════════════

def create_html_viewer(
    structure_content: str,
    format_type: str,
    molecule_name: str,
    case: int
) -> str:
    """
    Create HTML file for 3D visualization
    
    Args:
        structure_content: PDB or MOL block content
        format_type: 'pdb' or 'mol'
        molecule_name: Name to display
        case: Case number (1, 2, or 3)
    
    Returns:
        Path to HTML file
    """
    ensure_py3dmol()
    
    # Escape quotes in structure
    structure_escaped = structure_content.replace("'", "\\'").replace("\n", "\\n")
    
    case_info = {
        1: "Small Molecule (RDKit 3D Conformer)",
        2: "Protein Structure (ESMFold)",
        3: "Molecular Docking (DiffDock)"
    }
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
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
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 1200px;
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .case-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 20px;
            margin-top: 10px;
            font-weight: bold;
        }}
        .content {{
            display: flex;
            gap: 20px;
            padding: 30px;
        }}
        .viewer-section {{
            flex: 1;
            min-height: 600px;
        }}
        #viewer {{
            width: 100%;
            height: 100%;
            position: relative;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            background: #f5f5f5;
            min-height: 600px;
        }}
        .info-section {{
            width: 300px;
            background: #f9f9f9;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
        }}
        .info-section h3 {{
            margin-bottom: 15px;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .info-item {{
            margin-bottom: 12px;
            padding: 10px;
            background: white;
            border-radius: 5px;
            border-left: 3px solid #667eea;
        }}
        .info-label {{
            font-weight: bold;
            color: #333;
            font-size: 0.9em;
        }}
        .info-value {{
            color: #666;
            margin-top: 5px;
            word-break: break-all;
            font-size: 0.85em;
        }}
        .controls {{
            margin-top: 20px;
            padding: 15px;
            background: white;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
        }}
        .controls h4 {{
            margin-bottom: 10px;
            color: #667eea;
        }}
        .button-group {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        button {{
            padding: 10px 15px;
            border: none;
            border-radius: 5px;
            background: #667eea;
            color: white;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.3s;
        }}
        button:hover {{
            background: #764ba2;
        }}
        button.secondary {{
            background: #999;
        }}
        button.secondary:hover {{
            background: #777;
        }}
        .status {{
            padding: 15px;
            background: #e8f5e9;
            color: #2e7d32;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #4caf50;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        @media (max-width: 768px) {{
            .content {{
                flex-direction: column;
            }}
            .info-section {{
                width: 100%;
            }}
            .header h1 {{
                font-size: 1.8em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Virtual Drug Discovery Lab</h1>
            <p>3D Molecular Structure Viewer</p>
            <div class="case-badge">CASE {case}: {case_info.get(case, 'Unknown')}</div>
        </div>
        
        <div class="content">
            <div class="viewer-section">
                <div id="viewer" style="width:100%; height:600px; position:relative;"></div>
                <div class="controls">
                    <h4>Visualization Controls</h4>
                    <div class="button-group">
                        <button onclick="setStyle('cartoon')">Cartoon</button>
                        <button onclick="setStyle('stick')">Stick</button>
                        <button onclick="setStyle('sphere')">Sphere</button>
                        <button onclick="setStyle('cartoon,cartoon')">Cartoon+Cartoon</button>
                        <button class="secondary" onclick="resetView()">Reset View</button>
                        <button class="secondary" onclick="toggleSpin()">Toggle Spin</button>
                    </div>
                </div>
            </div>
            
            <div class="info-section">
                <div class="status">
                    Success: Yes
                </div>
                
                <h3>Molecule Info</h3>
                <div class="info-item">
                    <div class="info-label">Name</div>
                    <div class="info-value">{molecule_name}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Case Type</div>
                    <div class="info-value">Case {case}: {case_info.get(case, 'Unknown')}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Format</div>
                    <div class="info-value">{format_type.upper()}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Structure Size</div>
                    <div class="info-value">{len(structure_content)} characters</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            Generated by Virtual Drug Discovery Lab | Powered by 3Dmol.js
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
            let data = {{
                pdb: structure
            }};
            
            viewer.addModel(structure, "{format_type.upper()}");
            viewer.zoomTo();
            setStyle('cartoon');
            viewer.render();
        }}
        
        function setStyle(style) {{
            if (viewer) {{
                viewer.setStyle({{}}, {{cartoon: {{}}}});
                
                if (style.includes('cartoon')) {{
                    viewer.setStyle({{}}, {{cartoon: {{color: 'spectrum'}}}});
                }} else if (style.includes('stick')) {{
                    viewer.setStyle({{}}, {{stick: {{colorscheme: 'Jmol'}}}});
                }} else if (style.includes('sphere')) {{
                    viewer.setStyle({{}}, {{sphere: {{}}}});
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
        
        // Initialize when page loads
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
    
    logger.info(f"[VISUALIZER] HTML created: {temp_path}")
    return temp_path


def display_structure(
    structure_content: str,
    format_type: str,
    molecule_name: str,
    case: int,
    auto_open: bool = True
) -> str:
    """
    Display 3D structure in browser
    
    Args:
        structure_content: PDB or MOL block
        format_type: 'pdb' or 'mol'
        molecule_name: Name to display
        case: Case number
        auto_open: Auto-open in browser
    
    Returns:
        Path to HTML file
    """
    html_path = create_html_viewer(
        structure_content,
        format_type,
        molecule_name,
        case
    )
    
    if auto_open:
        webbrowser.open('file://' + os.path.realpath(html_path))
        logger.info(f"[VISUALIZER] Opened in browser: {html_path}")
    
    return html_path


# ═══════════════════════════════════════════════════════════════
# PYMOL EXPORT (Optional - requires PyMOL)
# ═══════════════════════════════════════════════════════════════

def export_to_pymol(
    structure_content: str,
    format_type: str,
    output_path: str
) -> bool:
    """
    Export structure to file for PyMOL
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(structure_content)
        logger.info(f"[VISUALIZER] Exported to PyMOL: {output_path}")
        return True
    except Exception as e:
        logger.error(f"[VISUALIZER] Export failed: {e}")
        return False