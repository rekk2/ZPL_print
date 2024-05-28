from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
import json
import os
import requests
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a random secret key

# Single printer IP address
printer_ip = "xxx.xxx.xxx.xxx"

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
    printer_status = check_printer_status(printer_ip)
    label_data = load_label_data()
    message = request.args.get('message')
    response = make_response(render_template('index.html', printer_status=printer_status, label_data=label_data, message=message))
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
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

@app.route('/print', methods=['POST'])
def print_label():
    selected_kit = request.form.get('kit_number')
    message = None

    label_data = load_label_data()
    zpl_code = ""
    if selected_kit in label_data:
        for part, part_data in label_data[selected_kit].items():
            zpl_code += generate_zpl(part_data['part_number'], part_data['description']) + "\n"
    else:
        return jsonify({'message': f"Kit {selected_kit} not found."})

    if zpl_code:
        try:
            response = send_zpl_to_printer(zpl_code)
            if response.status_code == 200:
                message = f"Kit {selected_kit} printed successfully!"
            else:
                message = f"Failed to print kit. Status code: {response.status_code}"
        except Exception as e:
            message = f"Failed to print kit. Error: {e}"

    return jsonify({'message': message})

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
            response = send_zpl_to_printer(zpl_code)
            if response.status_code == 200:
                message = f"Selected parts from kit {selected_kit} printed successfully!"
            else:
                message = f"Failed to print selected parts. Status code: {response.status_code}"
        except Exception as e:
            message = f"Failed to print selected parts. Error: {e}"

    return jsonify({'message': message})

def generate_zpl(part_number, description):
    zpl_template = """
    ^XA~TA000~JSN^LT0^MNW^MTD^PON^PMN^LH0,0^JMA^PR5,5~SD10^JUS^LRN^CI0^XZ
    ^XA
    ^MMT
    ^PW609
    ^LL0406
    ^LS0
    ^FT105,154^A0N,74,76^FH\\^FD{part_number}^FS
    ^FT49,198^A0N,28,110^FH\\^FD{description}^FS
    ^BY1,3,81^FT248,373^BCN,,Y,N
    ^FD>:>{part_number}^FS
    ^PQ1,0,1,Y^XZ
    """
    return zpl_template.format(part_number=part_number, description=description)

def send_zpl_to_printer(zpl_code):
    url = f"http://{printer_ip}:9100"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=zpl_code, headers=headers)
    return response

def check_printer_status(printer_ip):
    response = os.system(f"ping -n 1 {printer_ip}")  # For Windows, use "ping -n 1 {printer_ip}"
    if response == 0:
        return "green"
    else:
        return "red"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
