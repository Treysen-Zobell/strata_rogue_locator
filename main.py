import tkinter as tk
from tkinter import ttk
import sv_ttk
from api.cms import CMSClient
from time import sleep
import threading
import json


class EntryWithPlaceholder(tk.Entry):
    def __init__(self, master=None, placeholder="PLACEHOLDER", color='grey', **kwargs):
        super().__init__(master, kwargs)

        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = self['fg']

        self.bind("<FocusIn>", self.foc_in)
        self.bind("<FocusOut>", self.foc_out)

        self.put_placeholder()

    def put_placeholder(self):
        self.insert(0, self.placeholder)
        self['fg'] = self.placeholder_color

    def foc_in(self, *args):
        if self['fg'] == self.placeholder_color:
            self.delete('0', 'end')
            self['fg'] = self.default_fg_color

    def foc_out(self, *args):
        if not self.get():
            self.put_placeholder()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.geometry("400x500")
        self.root.title("Rogue Locator")

        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(3, weight=1)

        self.vertical_spacing = 2
        self.title_font = ("Arial", 14)
        self.body_font = ("Arial", 12)

        tk.Label(self.root, text="CMS Login", font=self.title_font)\
            .grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)

        tk.Label(self.root, text="CMS IP", font=self.body_font).grid(row=1, column=1, padx=5)
        self.cms_ip_entry = EntryWithPlaceholder(self.root, "10.225.254.105", font=self.body_font, fg="white")
        self.cms_ip_entry.grid(row=1, column=2, padx=5)

        tk.Label(self.root, text="CMS Username", font=self.body_font).grid(row=2, column=1, padx=5)
        self.cms_username_entry = EntryWithPlaceholder(self.root, "", font=self.body_font, fg="white")
        self.cms_username_entry.grid(row=2, column=2, padx=5)

        tk.Label(self.root, text="CMS Password", font=self.body_font).grid(row=3, column=1, padx=5)
        self.cms_password_entry = EntryWithPlaceholder(self.root, "", font=self.body_font, fg="white", show="*")
        self.cms_password_entry.grid(row=3, column=2, padx=5)

        tk.Label(self.root, text="Scan Range", font=self.title_font)\
            .grid(row=4, column=1, columnspan=2, sticky="ew", pady=5, padx=5)

        tk.Label(self.root, text="Node ID", font=self.body_font).grid(row=5, column=1, padx=5)
        self.node_id_entry = EntryWithPlaceholder(self.root, "rsvt-pon-1", font=self.body_font, fg="white")
        self.node_id_entry.grid(row=5, column=2, padx=5)

        tk.Label(self.root, text="ONT ID Start", font=self.body_font).grid(row=6, column=1, padx=5)
        self.ont_start_entry = EntryWithPlaceholder(self.root, "18301", font=self.body_font, fg="white")
        self.ont_start_entry.grid(row=6, column=2, padx=5)

        tk.Label(self.root, text="ONT ID Stop", font=self.body_font).grid(row=7, column=1)
        self.ont_stop_entry = EntryWithPlaceholder(self.root, "18332", font=self.body_font, fg="white")
        self.ont_stop_entry.grid(row=7, column=2, padx=5)

        ttk.Separator(self.root).grid(row=8, column=1, columnspan=2, pady=10, padx=5)

        self.scan_progressbar = ttk.Progressbar(self.root)
        self.scan_progressbar.grid(row=9, column=1, columnspan=2, padx=15, ipady=10, sticky="ew")

        self.scan_button = tk.Button(self.root, text="Scan", font=self.body_font,
                                     command=lambda: threading.Thread(target=locate_rogue, args=(self,)).start())
        self.scan_button.grid(row=10, column=1, columnspan=2, padx=15, pady=2, sticky="ew")

        self.results_canvas = tk.Canvas(self.root)
        self.results_canvas.grid(row=11, column=1, columnspan=2, pady=10)

        sv_ttk.set_theme("dark")

        self.root.mainloop()


def locate_rogue(app):
    cms = CMSClient(app.cms_username_entry.get(), app.cms_password_entry.get(), app.cms_ip_entry.get())
    node_id = app.node_id_entry.get()
    ont_start = int(app.ont_start_entry.get())
    ont_stop = int(app.ont_stop_entry.get())

    total_errors = {}
    for i in range(ont_start, ont_stop + 1):
        info = cms.get_fiber_info(node_id, str(i))
        if "bip-err-up" in info and "bip-err-down" in info:
            total_errors[i] = int(info["bip-err-up"]) + int(info["bip-err-down"])
        else:
            total_errors[i] = -1
        app.scan_progressbar["value"] = ((i - ont_start) / (ont_stop - ont_start)) * 100
    total_errors = {k: v for k, v in sorted(total_errors.items(), key=lambda item: -item[1])}
    top_five = list(total_errors.keys())[slice(5)]
    text = "\n".join(f"{k} has {total_errors[k]} errors" for k in top_five)

    tk.Label(app.results_canvas, text=text, font=app.body_font)\
        .grid(row=0, sticky="ew")

    # format output

    cms.logout()


def main():
    app = App()


if __name__ == '__main__':
    main()
