/**
 * Virtual Drug Discovery Lab - Frontend
 * Gère l'interface web et les appels API
 */

let viewer = null;
let isSpinning = false;

const PRESETS = {
    aspirin: "I want to visualize the 3D structure of aspirin (acetylsalicylic acid). SMILES: CC(=O)Oc1ccccc1C(=O)O. It's a common anti-inflammatory drug.",
    ubiquitin: "I'm working with human ubiquitin protein. Sequence: MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT. I need its 3D structure for analysis.",
    docking: "I need to study molecular docking of aspirin (SMILES: CC(=O)Oc1ccccc1C(=O)O) on COX-2 protein (MNIFEMLRIDEGLRLKIYKDTEGYYTIGIGHLLTKSPSLNAAKSELDKAIGRNTNGVITKDEAEKLFNQDVDAATRWGRRISRIQTGIVTSDFTNT). I want to see how the molecule binds to the active site."
};

/**
 * Charge un preset
 */
function loadPreset(name) {
    const text = PRESETS[name];
    if (text) {
        document.getElementById('description').value = text;
        // Auto-focus
        document.getElementById('description').focus();
    }
}

/**
 * Soumet la query
 */
async function submitQuery() {
    const description = document.getElementById('description').value.trim();
    
    if (!description) {
        showError('Please enter a description or molecule name');
        return;
    }

    // Désactiver le bouton
    const submitBtn = document.getElementById('submitBtn');
    submitBtn.disabled = true;
    document.getElementById('btnText').classList.add('hidden');
    document.getElementById('btnSpinner').classList.remove('hidden');
    hideError();

    try {
        console.log('[APP] Submitting query...');

        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                description: description
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Server error');
        }

        const result = await response.json();
        console.log('[APP] Response received:', result);

        if (result.success) {
            displayResults(result.data);
        } else {
            showError(result.error);
        }

    } catch (error) {
        console.error('[APP] Error:', error);
        showError(error.message);
    } finally {
        submitBtn.disabled = false;
        document.getElementById('btnText').classList.remove('hidden');
        document.getElementById('btnSpinner').classList.add('hidden');
    }
}

/**
 * Affiche les résultats
 */
function displayResults(data) {
    const resultsSection = document.getElementById('resultsSection');
    resultsSection.classList.remove('hidden');

    // Case badge
    const caseNum = data.ranker.case;
    const caseName = ['', 'Small Molecule', 'Protein', 'Docking Complex'][caseNum];
    document.getElementById('caseBadge').innerHTML = 
        `<strong>CASE ${caseNum}</strong> — ${caseName}`;

    // Ranker info
    displayRankerInfo(data.ranker);

    // Metrics
    displayMetrics(data.metrics);

    // 3D Viewer
    if (data.printer.success && data.printer.structure) {
        display3DStructure(
            data.printer.structure,
            data.printer.format,
            data.ranker.validation.molecule_name
        );
    }

    // Chemistry info
    displayChemInfo(data.ranker.validation);

    // Scroll vers résultats
    setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }, 100);
}

/**
 * Affiche infos Ranker
 */
// static/app.js — FIX SMILES DISPLAY
// ═══════════════════════════════════════════════════════════════

function displayRankerInfo(ranker) {
    const container = document.getElementById('rankerInfo');
    const v = ranker.validation;

    let html = `
        <div class="info-item">
            <div class="info-label">Case</div>
            <div class="info-value">Case ${ranker.case}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Model</div>
            <div class="info-value">${ranker.model}</div>
        </div>
        <div class="info-item">
            <div class="info-label">Confidence</div>
            <div class="info-value">${(ranker.confidence * 100).toFixed(0)}%</div>
        </div>
        <div class="info-item">
            <div class="info-label">Molecule Name</div>
            <div class="info-value">${v.molecule_name}</div>
        </div>
    `;

    // ✅ FIX: Display SMILES without word-break
    if (v.has_smiles && v.smiles) {
        // Escape HTML special chars
        const smiles_escaped = v.smiles
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        html += `
            <div class="info-item">
                <div class="info-label">SMILES</div>
                <div class="info-value smiles-display" title="${smiles_escaped}">
                    <code>${smiles_escaped}</code>
                </div>
            </div>
        `;
    }

    if (v.has_protein_sequence) {
        html += `
            <div class="info-item">
                <div class="info-label">Protein Length</div>
                <div class="info-value">${v.sequence_length} AA</div>
            </div>
        `;
    }

    container.innerHTML = html;
}

/**
 * Affiche les métriques
 */
function displayMetrics(metrics) {
    const container = document.getElementById('metricsInfo');

    const items = [
        { label: 'Ranker Score', value: metrics.ranker.global, status: metrics.ranker.status },
        { label: 'Printer Score', value: metrics.printer.global, status: metrics.printer.status },
        { label: 'Pipeline Score', value: metrics.pipeline.global, status: metrics.pipeline.status }
    ];

    let html = '';
    items.forEach(item => {
        const percentage = (item.value * 100).toFixed(0);
        const color = item.value >= 0.9 ? '#4caf50' : item.value >= 0.75 ? '#667eea' : '#ff9800';
        
        html += `
            <div class="metric-item">
                <div class="metric-label">${item.label}</div>
                <div class="metric-value" style="color: ${color}">${percentage}%</div>
                <div class="metric-bar">
                    <div class="metric-fill" style="width: ${percentage}%; background: ${color}"></div>
                </div>
                <div class="metric-label" style="font-size: 0.8em; color: #666;">${item.status}</div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Affiche la structure 3D
 */
/**
 * Affiche la structure 3D
 * FIX: Assure que le viewer est correctement initialisé dans le bon conteneur
 */
function display3DStructure(structure, format, moleculeName) {
    const element = document.getElementById('viewer');
    
    if (!element) {
        console.error('[3D] Viewer element not found!');
        return;
    }

    // Clear previous content
    element.innerHTML = '';

    try {
        // Créer le viewer DANS le conteneur
        const config = {
            backgroundColor: 'white',
            antialias: true,
            power_distance: 8.5
        };
        
        viewer = $3Dmol.createViewer(element, config);
        
        if (!viewer) {
            throw new Error('Failed to create viewer');
        }

        console.log('[3D] Viewer created successfully');

        // Ajouter le modèle
        viewer.addModel(structure, format.toUpperCase());
        console.log('[3D] Model added');

        // Zoom et render
        viewer.zoomTo();
        console.log('[3D] Zoomed to structure');

        // Style par défaut
        setStyle('stick');
        console.log('[3D] Style applied');

        // Force render
        viewer.render();
        console.log('[3D] Rendered successfully');

    } catch (e) {
        console.error('[3D] Error loading structure:', e);
        element.innerHTML = `
            <div style="
                padding: 20px;
                color: red;
                background: #ffebee;
                border-radius: 8px;
                text-align: center;
            ">
                <strong>Error loading 3D structure:</strong><br>
                ${e.message}
            </div>
        `;
    }
}

/**
 * Définit le style 3D
 * FIX: Ajoute des checks de sécurité
 */
function setStyle(styleName) {
    if (!viewer) {
        console.warn('[3D] Viewer not initialized');
        return;
    }

    try {
        // Clear all styles first
        viewer.setStyle({}, {});

        // Apply new style
        if (styleName === 'cartoon') {
            viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
            console.log('[3D] Style: cartoon');
        } 
        else if (styleName === 'stick') {
            viewer.setStyle({}, { stick: { colorscheme: 'Jmol' } });
            console.log('[3D] Style: stick');
        } 
        else if (styleName === 'sphere') {
            viewer.setStyle({}, { sphere: { colorscheme: 'Jmol' } });
            console.log('[3D] Style: sphere');
        } 
        else if (styleName === 'line') {
            viewer.setStyle({}, { line: {} });
            console.log('[3D] Style: line');
        }

        // Force render
        viewer.render();

    } catch (e) {
        console.error('[3D] Error setting style:', e);
    }
}

/**
 * Réinitialise la vue
 */
function resetView() {
    if (!viewer) {
        console.warn('[3D] Viewer not initialized');
        return;
    }

    try {
        viewer.zoomTo();
        viewer.render();
        console.log('[3D] View reset');
    } catch (e) {
        console.error('[3D] Error resetting view:', e);
    }
}

/**
 * Active/désactive la rotation
 */
function toggleSpin() {
    if (!viewer) {
        console.warn('[3D] Viewer not initialized');
        return;
    }

    try {
        isSpinning = !isSpinning;
        viewer.spin(isSpinning);
        viewer.render();
        console.log('[3D] Spin:', isSpinning ? 'ON' : 'OFF');
    } catch (e) {
        console.error('[3D] Error toggling spin:', e);
    }
}

/**
 * Affiche les infos chimiques
 */
function displayChemInfo(validation) {
    const container = document.getElementById('chemInfo');
    let html = '';

    if (validation.mw) {
        html += `
            <div class="chem-item">
                <div class="info-label">Molecular Weight</div>
                <div class="info-value">${validation.mw} Da</div>
            </div>
        `;
    }

    if (validation.logp !== undefined) {
        html += `
            <div class="chem-item">
                <div class="info-label">LogP</div>
                <div class="info-value">${validation.logp}</div>
            </div>
        `;
    }

    if (validation.drug_likeness !== undefined) {
        html += `
            <div class="chem-item">
                <div class="info-label">Drug-likeness</div>
                <div class="info-value">${(validation.drug_likeness * 100).toFixed(0)}%</div>
            </div>
        `;
    }

    if (validation.experiment_intent) {
        html += `
            <div class="chem-item">
                <div class="info-label">Experiment Intent</div>
                <div class="info-value">${validation.experiment_intent}</div>
            </div>
        `;
    }

    container.innerHTML = html || '<p>No additional information available</p>';
}

/**
 * Gestion des erreurs
 */
function showError(message) {
    const errorDiv = document.getElementById('errorMsg');
    errorDiv.textContent = message;
    errorDiv.classList.remove('hidden');
}

function hideError() {
    document.getElementById('errorMsg').classList.add('hidden');
}

// Enter pour soumettre
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('description').addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            submitQuery();
        }
    });
});