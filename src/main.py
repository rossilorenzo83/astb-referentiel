"""ASTB Annuaire des Médecins STB - Interface graphique."""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
import threading

from .scanner import scan_and_parse
from .reader_excel import read_annuaire
from .merge import merge_all, enrich
from .writer_excel import write_excel


class ASTBApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ASTB - Annuaire des Médecins STB")
        self.root.resizable(True, True)
        self.root.minsize(560, 500)

        w, h = 580, 520
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

        self.input_files: list[str] = []
        self._build_ui()

    def _build_ui(self):
        frame = tk.Frame(self.root, padx=20, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(
            frame,
            text="ASTB - Annuaire des Médecins STB",
            font=("Calibri", 14, "bold"),
            fg="#2F5496",
        ).pack(pady=(0, 10))

        tk.Label(
            frame,
            text="Enrichissez ou créez un annuaire structuré de médecins",
            font=("Calibri", 9),
            fg="gray",
        ).pack(pady=(0, 12))

        # --- Existing annuaire (optional) ---
        tk.Label(frame, text="Annuaire existant (optionnel) :", anchor="w").pack(fill=tk.X)

        row_ann = tk.Frame(frame)
        row_ann.pack(fill=tk.X, pady=(2, 8))
        self.annuaire_var = tk.StringVar()
        self.annuaire_var.trace_add("write", self._on_annuaire_changed)
        tk.Entry(row_ann, textvariable=self.annuaire_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        tk.Button(row_ann, text="Parcourir", command=self._browse_annuaire).pack(
            side=tk.LEFT, padx=(5, 0)
        )

        # --- Input files list ---
        tk.Label(frame, text="Fichiers à importer :", anchor="w").pack(fill=tk.X)

        list_frame = tk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 5))

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.file_listbox = tk.Listbox(
            list_frame, height=5, selectmode=tk.EXTENDED,
            yscrollcommand=scrollbar.set, font=("Calibri", 9),
        )
        scrollbar.config(command=self.file_listbox.yview)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_row = tk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(0, 8))

        tk.Button(btn_row, text="+ Ajouter", command=self._add_files,
                  font=("Calibri", 9)).pack(side=tk.LEFT)
        tk.Button(btn_row, text="- Retirer", command=self._remove_selected,
                  font=("Calibri", 9)).pack(side=tk.LEFT, padx=(5, 0))

        self.file_count_var = tk.StringVar(value="Aucun fichier")
        tk.Label(btn_row, textvariable=self.file_count_var, fg="gray",
                 font=("Calibri", 9), anchor="e").pack(side=tk.RIGHT)

        # --- Origin field ---
        tk.Label(frame, text="Origine :", anchor="w").pack(fill=tk.X)
        self.origin_var = tk.StringVar()
        tk.Entry(frame, textvariable=self.origin_var, width=50,
                 font=("Calibri", 10)).pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            frame,
            text="(Ex: CHU Nantes - avril 2026. Sera enregistré dans la colonne Source)",
            fg="gray", font=("Calibri", 8), anchor="w",
        ).pack(fill=tk.X, pady=(0, 10))

        # --- Output directory ---
        tk.Label(frame, text="Dossier de sortie :", anchor="w").pack(fill=tk.X)

        row_out = tk.Frame(frame)
        row_out.pack(fill=tk.X, pady=(2, 12))
        self.output_var = tk.StringVar()
        tk.Entry(row_out, textvariable=self.output_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        tk.Button(row_out, text="Parcourir", command=self._browse_output).pack(
            side=tk.LEFT, padx=(5, 0)
        )

        default_output = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"
        )
        os.makedirs(default_output, exist_ok=True)
        self.output_var.set(default_output)

        # --- Generate/Enrich button ---
        self.gen_btn = tk.Button(
            frame,
            text="Générer l'annuaire",
            font=("Calibri", 11, "bold"),
            bg="#2F5496", fg="white",
            activebackground="#1F3864", activeforeground="white",
            command=self._generate,
            height=2, width=25,
        )
        self.gen_btn.pack(pady=(0, 8))

        # --- Status ---
        self.status_var = tk.StringVar(value="Prêt")
        tk.Label(frame, textvariable=self.status_var, anchor="w",
                 fg="gray", font=("Calibri", 9)).pack(fill=tk.X)

    def _on_annuaire_changed(self, *_args):
        """Update button text based on whether an annuaire is loaded."""
        if self.annuaire_var.get().strip():
            self.gen_btn.config(text="Enrichir l'annuaire")
        else:
            self.gen_btn.config(text="Générer l'annuaire")

    def _browse_annuaire(self):
        path = filedialog.askopenfilename(
            title="Sélectionner l'annuaire existant",
            filetypes=[("Fichiers Excel", "*.xlsx")],
        )
        if path:
            self.annuaire_var.set(path)

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Sélectionner des fichiers à importer",
            filetypes=[
                ("Documents Word et Excel", "*.docx *.xlsx"),
                ("Fichiers Word", "*.docx"),
                ("Fichiers Excel", "*.xlsx *.xls"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        for path in paths:
            if path not in self.input_files:
                self.input_files.append(path)
                self.file_listbox.insert(tk.END, os.path.basename(path))
        self._update_file_count()

    def _remove_selected(self):
        for idx in reversed(self.file_listbox.curselection()):
            self.file_listbox.delete(idx)
            del self.input_files[idx]
        self._update_file_count()

    def _update_file_count(self):
        n = len(self.input_files)
        if n == 0:
            self.file_count_var.set("Aucun fichier")
        elif n == 1:
            self.file_count_var.set("1 fichier")
        else:
            self.file_count_var.set(f"{n} fichiers")

    def _browse_output(self):
        path = filedialog.askdirectory(title="Sélectionner le dossier de sortie")
        if path:
            self.output_var.set(path)

    def _generate(self):
        annuaire_path = self.annuaire_var.get().strip()
        output_dir = self.output_var.get().strip()

        if not self.input_files and not annuaire_path:
            messagebox.showerror(
                "Erreur",
                "Veuillez ajouter au moins un fichier à importer\n"
                "ou sélectionner un annuaire existant."
            )
            return
        if not output_dir:
            messagebox.showerror("Erreur", "Veuillez sélectionner un dossier de sortie.")
            return

        # Validate files
        if annuaire_path and not os.path.isfile(annuaire_path):
            messagebox.showerror("Erreur", f"Annuaire introuvable :\n{annuaire_path}")
            return
        for path in self.input_files:
            if not os.path.isfile(path):
                messagebox.showerror("Erreur", f"Fichier introuvable :\n{path}")
                return

        self.gen_btn.config(state=tk.DISABLED)
        self.status_var.set("Traitement en cours...")

        origin = self.origin_var.get().strip()
        thread = threading.Thread(
            target=self._run_generation,
            args=(annuaire_path, list(self.input_files), origin, output_dir),
            daemon=True,
        )
        thread.start()

    def _run_generation(self, annuaire_path: str, input_files: list[str],
                        origin: str, output_dir: str):
        try:
            warnings = []

            # --- Parse new import files ---
            new_doctors = []
            for i, path in enumerate(input_files, 1):
                filename = os.path.basename(path)
                self._update_status(f"Lecture du fichier {i}/{len(input_files)} : {filename}")

                docs, warns = scan_and_parse(path)
                if not docs and not warns:
                    warnings.append(f"Format non reconnu, fichier ignoré : {filename}")
                    continue

                # Stamp the origin/source on imported doctors
                source_label = origin if origin else filename
                for doc in docs:
                    doc.source = source_label

                new_doctors.extend(docs)
                warnings.extend(warns)

            if annuaire_path:
                # --- Enrichment mode ---
                self._update_status("Lecture de l'annuaire existant...")
                existing, read_warns = read_annuaire(annuaire_path)
                warnings.extend(read_warns)

                if new_doctors:
                    self._update_status("Enrichissement de l'annuaire...")
                    merged, enrich_warns = enrich(existing, new_doctors)
                    warnings.extend(enrich_warns)
                else:
                    merged = existing
            else:
                # --- Generation from scratch ---
                self._update_status("Fusion et dédoublonnage...")
                merged, merge_warns = merge_all(new_doctors)
                warnings.extend(merge_warns)

            # Write output
            self._update_status("Écriture de l'annuaire...")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "Annuaire_Medecins_STB.xlsx")
            write_excel(merged, warnings, output_path)

            named_count = sum(1 for d in merged if d.nom)
            self._update_status(
                f"Terminé ! {named_count} médecins dans le fichier. "
                f"({len(warnings)} avertissements)"
            )

            self.root.after(0, lambda: self._ask_open(output_path))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Erreur", f"Une erreur est survenue :\n{str(e)}"
            ))
            self._update_status("Erreur lors du traitement.")

        finally:
            self.root.after(0, lambda: self.gen_btn.config(state=tk.NORMAL))

    def _update_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def _ask_open(self, path: str):
        result = messagebox.askyesno(
            "Annuaire généré",
            f"L'annuaire a été créé avec succès :\n{path}\n\nVoulez-vous l'ouvrir maintenant ?",
        )
        if result:
            _open_file(path)


def _open_file(path: str):
    """Open a file with the system's default application."""
    import subprocess
    import platform
    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


def main():
    root = tk.Tk()
    ASTBApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
