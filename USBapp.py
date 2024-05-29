from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
import json
import os
import win32print
import win32api
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a random secret key

# Printer name (replace with your printer's name)
printer_name = "ZQ520"

# Path to the JSON file that stores label data
label_data_path = "label_data.json"

def load_label_data():
    if os.path.exists(label_data_path):
        with open(label_data_path, 'r') as file:
            return json.load(file)
    return {}

def save_label_data(label_data):
    with open(label_data_path, 'w') as file:
        json.dump(label_data, file)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    label_data = load_label_data()
    message = request.args.get('message')
    response = make_response(render_template('index.html', label_data=label_data, message=message))
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and request.form['username'] == 'admin' and request.form['password'] == 'admin':
        session['logged_in'] = True
        return redirect(url_for('admin'))
    else:
        return render_template('login.html', error='Invalid Credentials. Please try again.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    label_data = load_label_data()
    return render_template('admin.html', label_data=label_data)

@app.route('/admin/store', methods=['POST'])
@login_required
def store_label_data():
    kit_number = request.form['kit_number']
    part_number = request.form['part_number']
    description = request.form['description']

    label_data = load_label_data()
    if kit_number not in label_data:
        label_data[kit_number] = {}
    label_data[kit_number][part_number] = {
        "part_number": part_number,
        "description": description
    }
    save_label_data(label_data)

    return redirect(url_for('admin'))

@app.route('/admin/delete', methods=['POST'])
@login_required
def delete_label_data():
    kit_number = request.form['kit_number']
    part_number = request.form['part_number']

    label_data = load_label_data()
    if kit_number in label_data and part_number in label_data[kit_number]:
        del label_data[kit_number][part_number]
        if not label_data[kit_number]:
            del label_data[kit_number]
        save_label_data(label_data)

    return redirect(url_for('admin'))

@app.route('/admin/move', methods=['POST'])
@login_required
def move_label_data():
    kit_number = request.form['kit_number']
    part_number = request.form['part_number']
    direction = request.form['direction']

    label_data = load_label_data()
    if kit_number in label_data and part_number in label_data[kit_number]:
        parts = list(label_data[kit_number].items())
        index = parts.index((part_number, label_data[kit_number][part_number]))
        if direction == 'up' and index > 0:
            parts[index], parts[index - 1] = parts[index - 1], parts[index]
        elif direction == 'down' and index < len(parts) - 1:
            parts[index], parts[index + 1] = parts[index + 1], parts[index]
        label_data[kit_number] = dict(parts)
        save_label_data(label_data)

    return redirect(url_for('admin'))

@app.route('/print-selected-parts', methods=['POST'])
def print_selected_parts():
    selected_parts = request.form.getlist('part_numbers')
    selected_kit = request.form.get('kit_number_parts')
    message = None

    label_data = load_label_data()
    zpl_code = ""
    if selected_kit in label_data:
        for part in selected_parts:
            if part in label_data[selected_kit]:
                part_data = label_data[selected_kit][part]
                zpl_code += generate_zpl(part_data['part_number'], part_data['description']) + "\n"
    else:
        return jsonify({'message': f"Kit {selected_kit} not found."})

    if zpl_code:
        try:
            send_zpl_to_printer(zpl_code)
            message = f"Selected parts from kit {selected_kit} printed successfully!"
        except Exception as e:
            message = f"Failed to print selected parts. Error: {e}"

    return jsonify({'message': message})

def generate_zpl(part_number, description):
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

    zpl_template = f"""
    ^XA
    ^PW609
    ^LL0406
    ^LS0
    ^FO{final_position},50^A0N,74,76^FD{{part_number}}^FS
    ^FO30,150^FB{description_width},5,10,C,0^A0N,28,28^FD{{description}}^FS
    ^FO50,300^BCN,100,Y,N,N
    ^FD{{part_number}}^FS
    ^PQ1,0,1,Y
    ^XZ
    """
    return zpl_template.format(part_number=part_number, description=description)

def send_zpl_to_printer(zpl_code):
    # Send ZPL to the USB printer
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
