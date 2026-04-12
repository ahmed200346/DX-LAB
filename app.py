import streamlit as st
import streamlit.components.v1 as components
import requests
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign
import base64

# --- 1. CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Bio-Agent 3D Printer",
    page_icon="🧪",
    layout="wide"
)

# --- 2. FONCTIONS DE L'AGENT (BACKEND) ---

def get_smiles(query):
    """Traduit un nom de médicament en SMILES ou retourne le SMILES direct."""
    if any(c in query for c in "=()#"): 
        return query
    
    url = f"https://cactus.nci.nih.gov/chemical/structure/{query}/smiles"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.text.strip()
        return None
    except:
        return None

def process_molecule(smiles):
    """Génère la structure 3D, optimise l'énergie et calcule le RMSD."""
    # Création et ajout des H
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None, None
    
    mol = Chem.AddHs(mol)
    
    # Génération 3D initiale (Embedding)
    AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    mol_brute = Chem.Mol(mol) # Copie pour comparer
    
    # Optimisation énergétique (MMFF94)
    AllChem.MMFFOptimizeMolecule(mol)
    
    # Calcul du score de relaxation
    rmsd = rdMolAlign.GetBestRMS(mol, mol_brute)
    
    return mol, round(rmsd, 4)

def show_mol_3d(mol, height=500):
    """Affiche la molécule dans un composant HTML interactif."""
    # Extraction du bloc MOL/SDF
    mblock = Chem.MolToMolBlock(mol)
    
    # Encodage en Base64 pour une transmission sécurisée au navigateur
    mblock_b64 = base64.b64encode(mblock.encode('utf-8')).decode('utf-8')
    
    # Script HTML/JS utilisant la bibliothèque 3Dmol.js
    html_content = f"""
    <div id="container-3dmol" style="height: {height}px; width: 100%; position: relative;"></div>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://3Dmol.org/build/3Dmol-min.js"></script>
    <script>
        $(function() {{
            let viewer = $3Dmol.createViewer($("#container-3dmol"), {{
                backgroundColor: "white"
            }});
            let data = atob("{mblock_b64}");
            viewer.addModel(data, "sdf");
            viewer.setStyle({{stick: {{colorscheme: 'Jmol'}}, sphere: {{radius: 0.3}}}});
            viewer.zoomTo();
            viewer.render();
        }});
    </script>
    """
    return components.html(html_content, height=height)

# --- 3. INTERFACE UTILISATEUR (FRONTEND) ---

st.title("🧪 Bio-Agent 3D Printer v1.0")
st.markdown("---")

# Barre latérale pour les entrées
with st.sidebar:
    st.header("⚙️ Paramètres")
    user_input = st.text_input("Nom du médicament (ex: Ibuprofen) ou SMILES :", "Aspirin")
    analyze_btn = st.button("Lancer l'Analyse 🚀")
    
    st.info("""
    **Note :** L'agent utilise RDKit pour l'optimisation physique (MMFF94) 
    et le NCI Resolver pour la traduction des noms.
    """)

# Zone principale d'affichage
if analyze_btn:
    with st.spinner("L'agent génère la structure 3D..."):
        # Étape 1 : Obtenir le SMILES
        smiles = get_smiles(user_input)
        
        if smiles:
            # Étape 2 : Traitement chimique
            mol, rmsd = process_molecule(smiles)
            
            if mol:
                # Étape 3 : Affichage des résultats
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("📊 Métriques de Qualité")
                    st.metric("Structure identifiée", user_input.capitalize())
                    st.metric("Score de Relaxation (RMSD)", f"{rmsd} Å")
                    st.write("**SMILES :**")
                    st.code(smiles)
                
                with col2:
                    st.subheader("📦 Exportation")
                    st.success("Structure optimisée prête !")
                    # Optionnel : Tu pourrais ajouter un bouton de téléchargement ici
                
                st.markdown("---")
                st.subheader("🖥️ Modèle 3D Interactif")
                st.caption("Utilisez la souris pour faire pivoter et la molette pour zoomer.")
                
                # Étape 4 : Visualisation
                show_mol_3d(mol)
                
            else:
                st.error("Erreur lors de la génération 3D (Embedding failed).")
        else:
            st.error(f"Impossible de trouver la structure pour '{user_input}'. Vérifiez l'orthographe (en anglais).")

else:
    st.write("👈 Entrez un nom de molécule dans la barre latérale pour commencer.")