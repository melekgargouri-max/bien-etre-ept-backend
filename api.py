from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime

# ==========================================
# 1. INITIALISATION & SÉCURITÉ
# ==========================================
app = FastAPI(
    title="API Bien-être EPT",
    description="Backend complet avec lecture, écriture et simulation d'authentification"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient("mongodb://localhost:27017/")
db = client["bien_etre_ept"]

def formater_document(doc):
    if doc:
        doc["_id"] = str(doc["_id"])
        if "utilisateur_id" in doc:
            doc["utilisateur_id"] = str(doc["utilisateur_id"])
    return doc

# ==========================================
# 2. MODÈLES DE DONNÉES (Pour les requêtes POST)
# ==========================================

# Modèle pour la connexion
class LoginRequest(BaseModel):
    email: str
    mot_de_passe: str

# Modèle pour enregistrer une nouvelle journée
class MesuresQuotidiennes(BaseModel):
    humeur: int
    niveau_stress: int
    heures_sommeil: float
    charge_travail_percue: int
    motivation: int
    activite_physique: bool

class NouveauSuivi(BaseModel):
    mesures: MesuresQuotidiennes
    journal: str
# Modèle pour ajouter une ressource d'urgence
class NouvelleRessource(BaseModel):
    nom: str
    type: str # ex: "Psychologue", "Numéro vert", "Service scolarité"
    contact: str # Numéro de téléphone ou email
    disponibilite: str # ex: "24/7", "Lundi-Vendredi 8h-17h"

# Modèle pour l'historique : quand un étudiant donne son avis sur un conseil
class FeedbackRecommandation(BaseModel):
    recommandation_id: str
    feedback_positif: bool # True (Aimé) ou False (Pas aimé)
    commentaire: str = "" # Optionnel
# ==========================================
# 3. ROUTES DE LECTURE (GET) - Existantes
# ==========================================

@app.get("/")
def accueil():
    return {"message": "API Bien-être EPT 100% Opérationnelle ! 🚀"}

@app.get("/etudiants")
def liste_etudiants(limite: int = 50):
    etudiants = list(db.utilisateurs.find().limit(limite))
    return [formater_document(e) for e in etudiants]

@app.get("/recommandations")
def liste_recommandations():
    recos = list(db.recommandations.find())
    return [formater_document(r) for r in recos]

@app.get("/etudiants/{etudiant_id}")
def profil_etudiant(etudiant_id: str):
    try:
        etudiant = db.utilisateurs.find_one({"_id": ObjectId(etudiant_id)})
        if not etudiant:
            raise HTTPException(status_code=404, detail="Étudiant introuvable")
        return formater_document(etudiant)
    except Exception:
        raise HTTPException(status_code=400, detail="Format d'ID invalide")

@app.get("/etudiants/{etudiant_id}/suivi")
def suivi_etudiant(etudiant_id: str):
    try:
        suivis = list(db.suivi_quotidien.find({"utilisateur_id": ObjectId(etudiant_id)}).sort("date_mesure", -1))
        return [formater_document(s) for s in suivis]
    except Exception:
        raise HTTPException(status_code=400, detail="Erreur serveur")

@app.get("/etudiants/{etudiant_id}/objectifs")
def objectifs_etudiant(etudiant_id: str):
    try:
        objectifs = list(db.objectifs.find({"utilisateur_id": ObjectId(etudiant_id)}))
        return [formater_document(o) for o in objectifs]
    except Exception:
        raise HTTPException(status_code=400, detail="Erreur serveur")

@app.get("/statistiques/stress-moyen")
def stats_stress_moyen():
    pipeline = [{"$group": {"_id": None, "stress_moyen": {"$avg": "$mesures.niveau_stress"}}}]
    resultat = list(db.suivi_quotidien.aggregate(pipeline))
    if resultat:
         return {"stress_moyen_ept": round(resultat[0]["stress_moyen"], 2)}
    return {"stress_moyen_ept": 0}

# ==========================================
# 4. ROUTES D'ÉCRITURE (POST) - Nouvelles !
# ==========================================

@app.post("/auth/login")
def connexion(credentials: LoginRequest):
    """
    Simulation de connexion. Nos faux étudiants n'ayant pas de mot de passe en base,
    cette route valide simplement le format de la requête pour le frontend.
    """
    # Dans un vrai projet, on chercherait l'utilisateur dans la base et on vérifierait le hash du mot de passe
    if "@" not in credentials.email:
        raise HTTPException(status_code=400, detail="Email invalide")
    
    return {
        "message": "Connexion réussie", 
        "token": "faux_token_de_securite_12345",
        "utilisateur": credentials.email
    }

@app.post("/etudiants/{etudiant_id}/suivi")
def ajouter_suivi(etudiant_id: str, donnees: NouveauSuivi):
    """Permet d'ajouter une nouvelle journée (humeur, journal...) pour un étudiant."""
    try:
        nouveau_document = {
            "utilisateur_id": ObjectId(etudiant_id),
            "date_mesure": datetime.now(),
            "mesures": donnees.mesures.dict(),
            "journal": donnees.journal,
            "infrastructures_utilisees": [] # Vide par défaut pour simplifier l'ajout
        }
        
        # Insertion dans MongoDB
        resultat = db.suivi_quotidien.insert_one(nouveau_document)
        
        return {
            "message": "Journée enregistrée avec succès !", 
            "id_suivi": str(resultat.inserted_id)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail="Erreur lors de l'enregistrement des données")
    # ==========================================
# 5. RESSOURCES D'URGENCE ET FEEDBACK
# ==========================================

@app.get("/ressources-urgence")
def liste_ressources():
    """Récupère tous les contacts d'urgence."""
    ressources = list(db.ressources_urgence.find())
    return [formater_document(r) for r in ressources]

@app.post("/ressources-urgence")
def ajouter_ressource(ressource: NouvelleRessource):
    """Ajoute un nouveau contact d'urgence (Administrateur seulement en principe)."""
    resultat = db.ressources_urgence.insert_one(ressource.dict())
    return {"message": "Ressource d'urgence ajoutée", "id": str(resultat.inserted_id)}

@app.post("/etudiants/{etudiant_id}/feedback-recommandation")
def ajouter_feedback(etudiant_id: str, feedback: FeedbackRecommandation):
    """Enregistre l'avis d'un étudiant sur une recommandation spécifique."""
    try:
        nouveau_feedback = {
            "utilisateur_id": ObjectId(etudiant_id),
            "recommandation_id": ObjectId(feedback.recommandation_id),
            "date_feedback": datetime.now(),
            "feedback_positif": feedback.feedback_positif,
            "commentaire": feedback.commentaire
        }
        db.historique_recommandations.insert_one(nouveau_feedback)
        return {"message": "Merci pour votre retour ! Historique mis à jour."}
    except Exception:
        raise HTTPException(status_code=400, detail="Erreur lors de l'ajout du feedback")