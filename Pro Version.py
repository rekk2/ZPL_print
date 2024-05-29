import os
import win32print
import tkinter as tk
from tkinter import ttk, messagebox
import json
import socket

# Default printer name (can be changed by the user)
default_printer_name = "Zebra"

# Path to the JSON file that stores label data
label_data_path = "label_data.json"

class LabelPrintApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Label Print App")
        self.geometry("800x600")

        self.label_data = self.load_label_data()

        self.printer_name_var = tk.StringVar(value=default_printer_name)
        self.printer_ip_var = tk.StringVar()
        self.use_tcp_ip_var = tk.BooleanVar()

        self.create_tabs()

    def create_tabs(self):
        tab_control = ttk.Notebook(self)

        main_tab = ttk.Frame(tab_control)
        admin_tab = ttk.Frame(tab_control)

        tab_control.add(main_tab, text="Main")
        tab_control.add(admin_tab, text="Admin")

        tab_control.pack(expand=1, fill="both")

        self.create_main_tab(main_tab)
        self.create_admin_tab(admin_tab)

    def create_main_tab(self, tab):
        self.kit_number_var = tk.StringVar()
        self.message_var = tk.StringVar()

        # Printer selection options
        printer_frame = tk.Frame(tab)
        printer_frame.pack(pady=10)

        tk.Label(printer_frame, text="Printer Name (USB):").grid(row=0, column=0, sticky="w", padx=5)
        self.usb_entry = tk.Entry(printer_frame, textvariable=self.printer_name_var)
        self.usb_entry.grid(row=1, column=0, padx=5)

        tk.Checkbutton(printer_frame, text="Use TCP/IP Printer", variable=self.use_tcp_ip_var, command=self.toggle_tcp_ip).grid(row=0, column=1, padx=5)
        tk.Label(printer_frame, text="Printer IP Address (TCP/IP):").grid(row=0, column=2, sticky="w", padx=5)
        self.ip_entry = tk.Entry(printer_frame, textvariable=self.printer_ip_var)
        self.ip_entry.grid(row=1, column=2, padx=5)
        self.ip_entry.config(state=tk.DISABLED)

        self.part_vars = {}
        self.part_checkbuttons = []

        # Add a scrollable frame for parts
        self.part_frame = tk.Frame(tab)
        self.part_frame.pack(pady=10, expand=True, fill="both")

        part_canvas = tk.Canvas(self.part_frame)
        scrollbar = ttk.Scrollbar(self.part_frame, orient="vertical", command=part_canvas.yview)
        self.scrollable_part_frame = ttk.Frame(part_canvas)

        self.scrollable_part_frame.bind(
            "<Configure>",
            lambda e: part_canvas.configure(
                scrollregion=part_canvas.bbox("all")
            )
        )

        part_canvas.create_window((0, 0), window=self.scrollable_part_frame, anchor="nw")
        part_canvas.configure(yscrollcommand=scrollbar.set)

        part_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Label(tab, text="Select Kit:").pack(pady=10)
        self.kit_select = ttk.Combobox(tab, textvariable=self.kit_number_var, state="readonly")
        self.kit_select['values'] = list(self.label_data.keys())
        self.kit_select.pack()

        self.kit_select.bind("<<ComboboxSelected>>", self.update_parts)

        tk.Button(tab, text="Print Selected Parts", command=self.print_selected_parts).pack(pady=10)
        tk.Label(tab, textvariable=self.message_var).pack(pady=10)

    def toggle_tcp_ip(self):
        if self.use_tcp_ip_var.get():
            self.ip_entry.config(state=tk.NORMAL)
            self.usb_entry.config(state=tk.DISABLED)
        else:
            self.ip_entry.config(state=tk.DISABLED)
            self.usb_entry.config(state=tk.NORMAL)

    def update_parts(self, event=None):
        for cb in self.part_checkbuttons:
            cb.pack_forget()
        self.part_checkbuttons = []

        selected_kit = self.kit_number_var.get()
        if selected_kit in self.label_data:
            self.select_all_var = tk.BooleanVar(value=True)
            select_all_cb = tk.Checkbutton(self.scrollable_part_frame, text="All", variable=self.select_all_var, command=self.toggle_all_parts)
            select_all_cb.pack(anchor="w")
            self.part_checkbuttons.append(select_all_cb)

            for part_number, part_data in self.label_data[selected_kit].items():
                truncated_description = (part_data['description'][:50] + '...') if len(part_data['description']) > 50 else part_data['description']
                var = tk.BooleanVar(value=True)
                self.part_vars[part_number] = var
                cb = tk.Checkbutton(self.scrollable_part_frame, text=f"{part_number} - {truncated_description}", variable=var)
                cb.pack(anchor="w")
                self.part_checkbuttons.append(cb)

    def toggle_all_parts(self):
        check_all = self.select_all_var.get()
        for part_number, var in self.part_vars.items():
            var.set(check_all)

    def print_selected_parts(self):
        selected_kit = self.kit_number_var.get()
        if not selected_kit:
            self.message_var.set("Please select a kit.")
            return

        selected_parts = [part for part, var in self.part_vars.items() if var.get()]

        if not selected_parts:
            self.message_var.set("Please select at least one part.")
            return

        zpl_code = ""
        for part in selected_parts:
            part_data = self.label_data[selected_kit][part]
            zpl_code += self.generate_zpl(part_data['part_number'], part_data['description']) + "\n"

        if zpl_code:
            print(f"Sending ZPL to printer:\n{zpl_code}")  # Debug statement
            try:
                self.send_zpl_to_printer(zpl_code.strip())
                self.message_var.set("Selected parts printed successfully!")
            except Exception as e:
                self.message_var.set(f"Failed to print selected parts. Error: {e}")

    def create_admin_tab(self, tab):
        self.kit_number_admin_var = tk.StringVar()
        self.part_number_var = tk.StringVar()
        self.description_var = tk.StringVar()

        tk.Label(tab, text="Kit Number:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.kit_entry = tk.Entry(tab, textvariable=self.kit_number_admin_var)
        self.kit_entry.grid(row=1, column=0, padx=5, pady=5)

        tk.Label(tab, text="Part Number:").grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.part_entry = tk.Entry(tab, textvariable=self.part_number_var)
        self.part_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(tab, text="Description:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.desc_entry = tk.Entry(tab, textvariable=self.description_var)
        self.desc_entry.grid(row=1, column=2, padx=5, pady=5)

        tk.Button(tab, text="Add Part", command=self.store_label_data).grid(row=2, column=0, columnspan=3, padx=5, pady=10)

        self.admin_frame = tk.Frame(tab)
        self.admin_frame.grid(row=3, column=0, columnspan=3, sticky="nsew")

        tab.grid_rowconfigure(3, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_columnconfigure(2, weight=1)

        # Add a scrollbar to the admin frame
        self.admin_canvas = tk.Canvas(self.admin_frame)
        self.scrollbar = ttk.Scrollbar(self.admin_frame, orient="vertical", command=self.admin_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.admin_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.admin_canvas.configure(
                scrollregion=self.admin_canvas.bbox("all")
            )
        )

        self.admin_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.admin_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.admin_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.update_admin_tab()

    def update_admin_tab(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        row = 0
        for kit_number, parts in self.label_data.items():
            tk.Label(self.scrollable_frame, text=f"{kit_number}", font=('Arial', 12, 'bold')).grid(row=row, column=0, sticky="w", pady=5, columnspan=4)
            row += 1
            for part_number, part_data in parts.items():
                tk.Button(self.scrollable_frame, text="Delete", command=lambda kn=kit_number, pn=part_number: self.delete_label_data(kn, pn)).grid(row=row, column=0, padx=5)
                tk.Button(self.scrollable_frame, text="Up", command=lambda kn=kit_number, pn=part_number: self.move_label_data(kn, pn, 'up')).grid(row=row, column=1, padx=5)
                tk.Button(self.scrollable_frame, text="Down", command=lambda kn=kit_number, pn=part_number: self.move_label_data(kn, pn, 'down')).grid(row=row, column=2, padx=5)
                tk.Label(self.scrollable_frame, text=f"{part_data['part_number']} - {part_data['description']}", anchor="w").grid(row=row, column=3, sticky="w", padx=5)
                row += 1

    def store_label_data(self):
        kit_number = self.kit_number_admin_var.get()
        part_number = self.part_number_var.get()
        description = self.description_var.get()

        if not kit_number or not part_number or not description:
            messagebox.showerror("Error", "All fields are required.")
            return

        if kit_number not in self.label_data:
            self.label_data[kit_number] = {}

        self.label_data[kit_number][part_number] = {
            "part_number": part_number,
            "description": description
        }
        self.save_label_data()
        self.kit_select['values'] = list(self.label_data.keys())
        self.update_admin_tab()
        messagebox.showinfo("Success", f"Part {part_number} added to kit {kit_number}.")

    def delete_label_data(self, kit_number, part_number):
        if kit_number in self.label_data and part_number in self.label_data[kit_number]:
            del self.label_data[kit_number][part_number]
            if not self.label_data[kit_number]:
                del self.label_data[kit_number]
            self.save_label_data()
            self.kit_select['values'] = list(self.label_data.keys())
            self.update_admin_tab()
            messagebox.showinfo("Success", f"Part {part_number} deleted from kit {kit_number}.")
        else:
            messagebox.showerror("Error", "Part not found in the specified kit.")

    def move_label_data(self, kit_number, part_number, direction):
        if kit_number in self.label_data and part_number in self.label_data[kit_number]:
            parts = list(self.label_data[kit_number].items())
            index = parts.index((part_number, self.label_data[kit_number][part_number]))
            if direction == 'up' and index > 0:
                parts[index], parts[index - 1] = parts[index - 1], parts[index]
            elif direction == 'down' and index < len(parts) - 1:
                parts[index], parts[index + 1] = parts[index + 1], parts[index]
            self.label_data[kit_number] = dict(parts)
            self.save_label_data()
            self.update_admin_tab()
            messagebox.showinfo("Success", f"Part {part_number} moved {direction} in kit {kit_number}.")
        else:
            messagebox.showerror("Error", "Part not found in the specified kit.")

    def load_label_data(self):
        if os.path.exists(label_data_path):
            with open(label_data_path, 'r') as file:
                return json.load(file)
        return {}

    def save_label_data(self):
        with open(label_data_path, 'w') as file:
            json.dump(self.label_data, file)

    def generate_zpl(self, part_number, description):
        # Constants for label and font dimensions
        label_width = 609  # Width of the label in dots
        char_width = 74    # Width of a single character in dots (based on font size)
        description_width = 550  # Width for the description field block

        # Calculate the width of the part number text
        part_number_length = len(part_number)
        total_text_width = part_number_length * char_width

        # Calculate the centered position for the part number
        centered_position = (label_width - total_text_width) // 2

        # Adjust this value to fine-tune the left-right position
        fine_tune_adjustment = -60  # Increase this value to move right, decrease to move left
        final_position = centered_position + fine_tune_adjustment

        zpl_template = (
            f"^XA\n"
            f"^PW609\n"
            f"^LL0406\n"
            f"^LS0\n"
            f"^FO{final_position},50^A0N,74,76^FD{part_number}^FS\n"
            f"^FO30,150^FB{description_width},5,10,C,0^A0N,28,28^FD{description}^FS\n"
            f"^PQ1,0,1,Y\n"
            f"^XZ"
        )
        return zpl_template.format(part_number=part_number, description=description)

    def send_zpl_to_printer(self, zpl_code):
        if self.use_tcp_ip_var.get():
            printer_ip = self.printer_ip_var.get()
            try:
                # Send ZPL to the TCP/IP printer
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((printer_ip, 9100))
                sock.sendall(zpl_code.encode())
                sock.close()
            except Exception as e:
                raise Exception(f"Failed to print to TCP/IP printer at {printer_ip}: {e}")
        else:
            # Send ZPL to the USB printer
            printer_name = self.printer_name_var.get()
            hPrinter = win32print.OpenPrinter(printer_name)
            try:
                hJob = win32print.StartDocPrinter(hPrinter, 1, ("ZPL Label", None, "RAW"))
                try:
                    win32print.StartPagePrinter(hPrinter)
                    win32print.WritePrinter(hPrinter, zpl_code.encode())
                    win32print.EndPagePrinter(hPrinter)
                finally:
                    win32print.EndDocPrinter(hPrinter)
            finally:
                win32print.ClosePrinter(hPrinter)

if __name__ == "__main__":
    app = LabelPrintApp()
    app.mainloop()
