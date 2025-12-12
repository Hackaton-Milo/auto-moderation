# simple_gui.py
import tkinter as tk
from tkinter import ttk

def launch_gui_demopyth():
    BG_BLUE = "#0A0A87"
    CARD_WHITE = "#FFFFFF"

    root = tk.Tk()
    root.title("Simple GUI Test - Milo Style")
    root.geometry("800x600")
    root.configure(bg=BG_BLUE)

    # S'assurer que la fenêtre apparaisse au premier plan (utile parfois)
    root.lift()
    root.attributes('-topmost', True)
    root.after_idle(root.attributes, '-topmost', False)

    # Carte blanche centrale
    card = tk.Frame(root, bg=CARD_WHITE, bd=0, relief="flat")
    card.place(relx=0.5, rely=0.5, anchor="center", width=640, height=440)

    # Titre dans la carte
    title = tk.Label(card, text="Interface de démonstration", font=("Arial", 18, "bold"), bg=CARD_WHITE)
    title.pack(pady=(20, 10))

    # Sous-titre / instruction
    subtitle = tk.Label(card, text="Cette fenêtre confirme que la GUI fonctionne.", font=("Arial", 12), bg=CARD_WHITE)
    subtitle.pack(pady=(0, 20))

    # Exemple d'un champ texte et d'un bouton
    entry = tk.Entry(card, width=50)
    entry.insert(0, "Tapez quelque chose ici")
    entry.pack(pady=10)

    def on_click():
        value = entry.get()
        # afficher dans un label simple
        result_label.config(text=f"Vous avez tapé : {value}")

    run_btn = ttk.Button(card, text="Valider", command=on_click)
    run_btn.pack(pady=10)

    result_label = tk.Label(card, text="", bg=CARD_WHITE, font=("Arial", 11))
    result_label.pack(pady=(10, 0))

    # Footer discret
    footer = t
