"""
Prompts dédiés à l'agent Planner.
Chaque prompt utilise la technique Chain-of-Thought (CoT) pour une analyse
approfondie et structurée du besoin utilisateur.
"""

# ──────────────────────── Compréhension du besoin ────────────────────────

UNDERSTAND_NEED_PROMPT = """Tu es l'agent Planner, un expert en analyse des besoins et en planification
dans un système multi-agent.

**Besoin exprimé par l'utilisateur :**
{user_input}

**Instructions — Raisonnement Chain-of-Thought :**
Étape 1 : Lis attentivement l'intégralité du besoin exprimé.
Étape 2 : Identifie l'objectif principal (le résultat final attendu).
Étape 3 : Identifie les sous-objectifs implicites ou explicites.
Étape 4 : Identifie les contraintes mentionnées (délais, formats, technologies, etc.).
Étape 5 : Identifie les ambiguïtés ou les informations manquantes.
Étape 6 : Classifie le type de besoin (développement, analyse, recherche, création de contenu, etc.).
Étape 7 : Évalue la complexité globale (simple, modérée, complexe).

**Format de réponse (JSON strict) :**
{{
    "reasoning": "Ton raisonnement détaillé étape par étape, montrant comment tu as analysé chaque aspect du besoin",
    "main_objective": "L'objectif principal clairement formulé",
    "sub_objectives": ["sous_objectif_1", "sous_objectif_2"],
    "constraints": ["contrainte_1", "contrainte_2"],
    "ambiguities": ["ambiguïté_1", "ambiguïté_2"],
    "need_type": "development|analysis|research|content_creation|data_processing|other",
    "complexity": "simple|moderate|complex",
    "requires_clarification": false,
    "clarification_questions": []
}}
"""

# ──────────────────────── Génération du plan ────────────────────────

GENERATE_PLAN_PROMPT = """Tu es l'agent Planner. Tu dois maintenant générer un plan d'exécution
structuré et détaillé à partir de l'analyse du besoin.

**Analyse du besoin :**
{need_analysis}

**Agents disponibles dans le système :**
{available_agents}

**Instructions — Raisonnement Chain-of-Thought :**
Étape 1 : À partir de l'objectif principal, décompose le travail en étapes logiques.
Étape 2 : Pour chaque étape, détermine quel agent est le plus approprié.
Étape 3 : Identifie les dépendances entre les étapes (quelles étapes doivent être complétées avant d'autres).
Étape 4 : Définis des critères de succès mesurables pour chaque étape.
Étape 5 : Estime la complexité et la priorité de chaque étape.
Étape 6 : Identifie les étapes qui peuvent être exécutées en parallèle.
Étape 7 : Vérifie que le plan couvre tous les sous-objectifs identifiés.
Étape 8 : Ajoute des points de vérification (checkpoints) pour valider l'avancement.

**Format de réponse (JSON strict) :**
{{
    "reasoning": "Ton raisonnement détaillé étape par étape, expliquant la logique de décomposition du plan",
    "plan_title": "Titre descriptif du plan",
    "plan_description": "Description résumée du plan",
    "total_steps": 0,
    "estimated_complexity": "simple|moderate|complex",
    "steps": [
        {{
            "step_id": 1,
            "title": "Titre de l'étape",
            "description": "Description détaillée de ce qui doit être fait",
            "target_agent": "nom_agent",
            "dependencies": [],
            "input_required": "Données d'entrée nécessaires",
            "expected_output": "Résultat attendu",
            "success_criteria": ["critère_1", "critère_2"],
            "priority": "high|medium|low",
            "complexity": "simple|moderate|complex",
            "can_parallel": false
        }}
    ],
    "checkpoints": [
        {{
            "after_step": 0,
            "validation": "Description de la validation à effectuer"
        }}
    ],
    "risks": ["risque_1", "risque_2"],
    "fallback_strategies": ["stratégie_1", "stratégie_2"]
}}
"""

# ──────────────────────── Raffinement du plan ────────────────────────

REFINE_PLAN_PROMPT = """Tu es l'agent Planner. Tu dois affiner le plan d'exécution
suite à un retour (feedback) ou de nouvelles informations.

**Plan actuel :**
{current_plan}

**Feedback reçu :**
{feedback}

**Instructions — Raisonnement Chain-of-Thought :**
Étape 1 : Analyse le feedback reçu et identifie les points à modifier.
Étape 2 : Évalue l'impact des modifications sur les étapes existantes.
Étape 3 : Identifie les nouvelles dépendances créées.
Étape 4 : Ajuste les priorités et l'ordre d'exécution si nécessaire.
Étape 5 : Vérifie que le plan modifié reste cohérent et réalisable.

**Format de réponse (JSON strict) :**
{{
    "reasoning": "Ton raisonnement détaillé sur les modifications apportées",
    "changes_made": ["changement_1", "changement_2"],
    "updated_plan": {{
        "plan_title": "Titre du plan mis à jour",
        "steps": [
            {{
                "step_id": 1,
                "title": "Titre de l'étape",
                "description": "Description mise à jour",
                "target_agent": "nom_agent",
                "dependencies": [],
                "priority": "high|medium|low",
                "status": "pending|modified|new|removed"
            }}
        ]
    }},
    "impact_assessment": "Évaluation de l'impact des changements"
}}
"""
