"""
Explorateur de Fichiers - Tkinter
Projet scolaire - OFPPT

Fonctionnalités :
- Navigation dans l'arborescence du PC (dossiers à gauche, contenu à droite)
- Boutons Précédent / Suivant / Dossier parent / Actualiser
- Barre d'adresse éditable
- Double-clic pour ouvrir un dossier ou un fichier (avec l'application par défaut)
- Détails des fichiers : taille, type, date de modification
- Menu clic droit : ouvrir, renommer, supprimer, nouveau dossier
"""

import os
import platform
import subprocess
import shutil
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


def formater_taille(taille_octets):
    """Convertit une taille en octets vers un format lisible (Ko, Mo, Go)."""
    if taille_octets is None:
        return ""
    for unite in ["o", "Ko", "Mo", "Go", "To"]:
        if taille_octets < 1024:
            return f"{taille_octets:.1f} {unite}" if unite != "o" else f"{int(taille_octets)} {unite}"
        taille_octets /= 1024
    return f"{taille_octets:.1f} Po"


class ExplorateurFichiers(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Explorateur de Fichiers")
        self.geometry("1100x650")

        self.historique = []       # chemins visités
        self.position_historique = -1
        self.dossier_actuel = os.path.expanduser("~")  # dossier utilisateur par défaut

        self.creer_barre_navigation()
        self.creer_zone_principale()

        self.naviguer_vers(self.dossier_actuel, garder_historique=True)

    # ------------------------------------------------------------------
    # BARRE DE NAVIGATION
    # ------------------------------------------------------------------
    def creer_barre_navigation(self):
        cadre = ttk.Frame(self)
        cadre.pack(fill="x", padx=8, pady=8)

        self.btn_precedent = ttk.Button(cadre, text="◀", width=3, command=self.aller_precedent)
        self.btn_precedent.pack(side="left", padx=2)

        self.btn_suivant = ttk.Button(cadre, text="▶", width=3, command=self.aller_suivant)
        self.btn_suivant.pack(side="left", padx=2)

        ttk.Button(cadre, text="▲ Parent", command=self.aller_parent).pack(side="left", padx=2)
        ttk.Button(cadre, text="⟳ Actualiser", command=self.actualiser).pack(side="left", padx=2)
        ttk.Button(cadre, text="🏠 Accueil", command=self.aller_accueil).pack(side="left", padx=2)
        ttk.Button(cadre, text="📁 Nouveau dossier", command=self.creer_dossier).pack(side="left", padx=8)

        self.var_adresse = tk.StringVar()
        entree_adresse = ttk.Entry(cadre, textvariable=self.var_adresse)
        entree_adresse.pack(side="left", fill="x", expand=True, padx=8)
        entree_adresse.bind("<Return>", lambda e: self.naviguer_vers(self.var_adresse.get()))

        ttk.Button(cadre, text="Aller", command=lambda: self.naviguer_vers(self.var_adresse.get())).pack(
            side="left", padx=2
        )

    # ------------------------------------------------------------------
    # ZONE PRINCIPALE : arborescence à gauche + contenu à droite
    # ------------------------------------------------------------------
    def creer_zone_principale(self):
        conteneur = ttk.Panedwindow(self, orient="horizontal")
        conteneur.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # --- Arborescence des dossiers (racines / lecteurs) ---
        cadre_arbre = ttk.Frame(conteneur, width=250)
        self.arbre_dossiers = ttk.Treeview(cadre_arbre, show="tree")
        self.arbre_dossiers.pack(fill="both", expand=True)
        self.arbre_dossiers.bind("<<TreeviewOpen>>", self.developper_dossier)
        self.arbre_dossiers.bind("<<TreeviewSelect>>", self.selection_arbre)
        conteneur.add(cadre_arbre, weight=1)

        self.initialiser_racines()

        # --- Liste des fichiers/dossiers du dossier courant ---
        cadre_liste = ttk.Frame(conteneur)
        colonnes = ("nom", "type", "taille", "modifie")
        self.liste = ttk.Treeview(cadre_liste, columns=colonnes, show="headings", selectmode="extended")

        self.liste.heading("nom", text="Nom")
        self.liste.heading("type", text="Type")
        self.liste.heading("taille", text="Taille")
        self.liste.heading("modifie", text="Modifié le")

        self.liste.column("nom", width=320)
        self.liste.column("type", width=100, anchor="center")
        self.liste.column("taille", width=100, anchor="e")
        self.liste.column("modifie", width=160, anchor="center")

        self.liste.pack(fill="both", expand=True)
        self.liste.bind("<Double-1>", self.double_clic_liste)
        self.liste.bind("<Button-3>", self.menu_contextuel)  # clic droit (Windows/Linux)
        self.liste.bind("<Button-2>", self.menu_contextuel)  # clic droit (certains macOS)

        conteneur.add(cadre_liste, weight=3)

        # --- Barre de statut ---
        self.var_statut = tk.StringVar(value="Prêt")
        ttk.Label(self, textvariable=self.var_statut, relief="sunken", anchor="w").pack(fill="x", side="bottom")

    def initialiser_racines(self):
        """Ajoute les lecteurs (Windows) ou la racine / (Linux/Mac) dans l'arborescence."""
        self.arbre_dossiers.delete(*self.arbre_dossiers.get_children())

        if platform.system() == "Windows":
            racines = [f"{lettre}:\\" for lettre in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                       if os.path.exists(f"{lettre}:\\")]
        else:
            racines = ["/"]

        for racine in racines:
            noeud = self.arbre_dossiers.insert("", "end", text=racine, values=(racine,), open=False)
            self.ajouter_placeholder(noeud)

    def ajouter_placeholder(self, noeud):
        """Ajoute un enfant factice pour permettre le clic '+' (chargement paresseux)."""
        self.arbre_dossiers.insert(noeud, "end", text="...")

    def developper_dossier(self, event):
        """Charge les sous-dossiers réels quand on ouvre un nœud de l'arborescence."""
        noeud = self.arbre_dossiers.focus()
        enfants = self.arbre_dossiers.get_children(noeud)

        # Si le seul enfant est le placeholder "...", on le remplace par les vrais sous-dossiers
        if len(enfants) == 1 and self.arbre_dossiers.item(enfants[0], "text") == "...":
            self.arbre_dossiers.delete(enfants[0])
            chemin_parent = self.chemin_du_noeud(noeud)
            try:
                for nom in sorted(os.listdir(chemin_parent)):
                    chemin_complet = os.path.join(chemin_parent, nom)
                    if os.path.isdir(chemin_complet):
                        sous_noeud = self.arbre_dossiers.insert(
                            noeud, "end", text=nom, values=(chemin_complet,), open=False
                        )
                        self.ajouter_placeholder(sous_noeud)
            except (PermissionError, OSError):
                pass

    def chemin_du_noeud(self, noeud):
        return self.arbre_dossiers.item(noeud, "values")[0]

    def selection_arbre(self, event):
        selection = self.arbre_dossiers.selection()
        if selection:
            chemin = self.chemin_du_noeud(selection[0])
            self.naviguer_vers(chemin)

    # ------------------------------------------------------------------
    # NAVIGATION
    # ------------------------------------------------------------------
    def naviguer_vers(self, chemin, garder_historique=True):
        chemin = os.path.normpath(chemin) if chemin else self.dossier_actuel

        if not os.path.isdir(chemin):
            messagebox.showerror("Erreur", f"Le dossier n'existe pas ou n'est pas accessible :\n{chemin}")
            return

        self.dossier_actuel = chemin
        self.var_adresse.set(chemin)

        if garder_historique:
            # On coupe l'historique "futur" si on navigue depuis une position antérieure
            self.historique = self.historique[: self.position_historique + 1]
            self.historique.append(chemin)
            self.position_historique = len(self.historique) - 1

        self.mettre_a_jour_boutons_historique()
        self.charger_contenu(chemin)

    def mettre_a_jour_boutons_historique(self):
        self.btn_precedent.config(state="normal" if self.position_historique > 0 else "disabled")
        self.btn_suivant.config(
            state="normal" if self.position_historique < len(self.historique) - 1 else "disabled"
        )

    def aller_precedent(self):
        if self.position_historique > 0:
            self.position_historique -= 1
            self.naviguer_vers(self.historique[self.position_historique], garder_historique=False)
            self.mettre_a_jour_boutons_historique()

    def aller_suivant(self):
        if self.position_historique < len(self.historique) - 1:
            self.position_historique += 1
            self.naviguer_vers(self.historique[self.position_historique], garder_historique=False)
            self.mettre_a_jour_boutons_historique()

    def aller_parent(self):
        parent = os.path.dirname(self.dossier_actuel)
        if parent and parent != self.dossier_actuel:
            self.naviguer_vers(parent)

    def aller_accueil(self):
        self.naviguer_vers(os.path.expanduser("~"))

    def actualiser(self):
        self.charger_contenu(self.dossier_actuel)

    # ------------------------------------------------------------------
    # CONTENU DU DOSSIER (liste de droite)
    # ------------------------------------------------------------------
    def charger_contenu(self, chemin):
        for item in self.liste.get_children():
            self.liste.delete(item)

        try:
            entrees = list(os.scandir(chemin))
        except PermissionError:
            self.var_statut.set("Accès refusé à ce dossier.")
            return
        except OSError as e:
            self.var_statut.set(f"Erreur : {e}")
            return

        dossiers = sorted([e for e in entrees if e.is_dir()], key=lambda e: e.name.lower())
        fichiers = sorted([e for e in entrees if e.is_file()], key=lambda e: e.name.lower())

        for entree in dossiers:
            self.liste.insert(
                "", "end",
                values=(entree.name, "Dossier", "", self.date_modification(entree)),
                tags=("dossier",)
            )

        for entree in fichiers:
            try:
                taille = entree.stat().st_size
            except OSError:
                taille = None
            extension = os.path.splitext(entree.name)[1].lstrip(".").upper() or "Fichier"
            self.liste.insert(
                "", "end",
                values=(entree.name, extension, formater_taille(taille), self.date_modification(entree)),
                tags=("fichier",)
            )

        self.var_statut.set(f"{len(dossiers)} dossier(s), {len(fichiers)} fichier(s)")

    @staticmethod
    def date_modification(entree):
        try:
            horodatage = entree.stat().st_mtime
            return datetime.fromtimestamp(horodatage).strftime("%d/%m/%Y %H:%M")
        except OSError:
            return ""

    # ------------------------------------------------------------------
    # ACTIONS SUR LES FICHIERS/DOSSIERS
    # ------------------------------------------------------------------
    def double_clic_liste(self, event):
        selection = self.liste.selection()
        if not selection:
            return
        nom, type_, *_ = self.liste.item(selection[0], "values")
        chemin_complet = os.path.join(self.dossier_actuel, nom)

        if type_ == "Dossier":
            self.naviguer_vers(chemin_complet)
        else:
            self.ouvrir_fichier(chemin_complet)

    def ouvrir_fichier(self, chemin):
        """Ouvre le fichier avec l'application par défaut du système."""
        try:
            if platform.system() == "Windows":
                os.startfile(chemin)
            elif platform.system() == "Darwin":
                subprocess.run(["open", chemin])
            else:
                subprocess.run(["xdg-open", chemin])
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir le fichier :\n{e}")

    def menu_contextuel(self, event):
        item_id = self.liste.identify_row(event.y)
        if item_id:
            self.liste.selection_set(item_id)

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Ouvrir", command=self.action_ouvrir_selection)
        menu.add_command(label="Renommer", command=self.action_renommer)
        menu.add_command(label="Supprimer", command=self.action_supprimer)
        menu.add_separator()
        menu.add_command(label="Nouveau dossier ici", command=self.creer_dossier)
        menu.tk_popup(event.x_root, event.y_root)

    def action_ouvrir_selection(self):
        selection = self.liste.selection()
        if not selection:
            return
        nom, type_, *_ = self.liste.item(selection[0], "values")
        chemin_complet = os.path.join(self.dossier_actuel, nom)
        if type_ == "Dossier":
            self.naviguer_vers(chemin_complet)
        else:
            self.ouvrir_fichier(chemin_complet)

    def action_renommer(self):
        selection = self.liste.selection()
        if not selection:
            return
        ancien_nom, *_ = self.liste.item(selection[0], "values")
        nouveau_nom = simpledialog.askstring("Renommer", "Nouveau nom :", initialvalue=ancien_nom)
        if not nouveau_nom or nouveau_nom == ancien_nom:
            return
        try:
            os.rename(
                os.path.join(self.dossier_actuel, ancien_nom),
                os.path.join(self.dossier_actuel, nouveau_nom)
            )
            self.actualiser()
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible de renommer :\n{e}")

    def action_supprimer(self):
        selection = self.liste.selection()
        if not selection:
            return

        noms = [self.liste.item(item, "values")[0] for item in selection]
        if not messagebox.askyesno(
            "Confirmation",
            f"Supprimer définitivement {len(noms)} élément(s) ?\n\n" + "\n".join(noms[:10])
        ):
            return

        erreurs = []
        for nom in noms:
            chemin_complet = os.path.join(self.dossier_actuel, nom)
            try:
                if os.path.isdir(chemin_complet):
                    shutil.rmtree(chemin_complet)
                else:
                    os.remove(chemin_complet)
            except OSError as e:
                erreurs.append(f"{nom} : {e}")

        self.actualiser()
        if erreurs:
            messagebox.showwarning("Terminé avec erreurs", "\n".join(erreurs[:10]))

    def creer_dossier(self):
        nom = simpledialog.askstring("Nouveau dossier", "Nom du dossier :")
        if not nom:
            return
        try:
            os.mkdir(os.path.join(self.dossier_actuel, nom))
            self.actualiser()
        except OSError as e:
            messagebox.showerror("Erreur", f"Impossible de créer le dossier :\n{e}")


if __name__ == "__main__":
    app = ExplorateurFichiers()
    app.mainloop()
