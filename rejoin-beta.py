from flask import Flask, request, jsonify
import json
from datetime import datetime, timedelta
import os
import threading
import time
import subprocess
import requests

app = Flask(__name__)

user_data = {}

def get_pid(package):
    pid_cmd = f"pidof {package}"
    pid_output = subprocess.getoutput(pid_cmd)
    pid = pid_output.strip()

    if pid:
        return pid

def send_webhook(webhook_url, content, avatar_url=None):
    if webhook_url == "0":
        print("Webhook URL is set to 0, skipping the request.")
        return

    data = {
        "content": content,
        "username": "Staryuu Auto Rejoin",
    }
    
    if avatar_url:
        data["avatar_url"] = avatar_url
    
    response = requests.post(webhook_url, json=data)
    
    if response.status_code == 204:
        print("Message sent successfully")
    else:
        print(f"Failed to send message. Status code: {response.status_code}, response: {response.text}")

def launch_roblox_with_private_server(private_server_link, username):
    packagename = user_data.get(username, {}).get('packagename')
    crash = user_data.get(username, {}).get('cc')
    pid = get_pid(packagename)
    if packagename:
        if pid:
            close = f"su -c 'kill {pid}'"
            os.system(close)
        time.sleep(5)
        cmd = f"am start -a android.intent.action.VIEW -d '{private_server_link}' {packagename}"
        os.system(cmd)
        crash += 1
        user_data[username]['cc'] = crash
        print(f"Launched Roblox game with ps: {private_server_link} for user: {username} with crash count: {crash}")
    else:
        print(f"Package name not found for user: {username}")



def launch_roblox(game_id, username):
    packagename = user_data.get(username, {}).get('packagename')
    crash = user_data.get(username, {}).get('cc')
    pid = get_pid(packagename)
    if packagename:
        if pid:
            close = f"su -c 'kill {pid}'"
            os.system(close)
        time.sleep(5)
        url = f"roblox://placeID={game_id}"
        cmd = f"am start -a android.intent.action.VIEW -d '{url}' {packagename}"
        os.system(cmd)
        crash += 1
        user_data[username]['cc'] = crash
        print(f"Launched Roblox game with ID: {game_id} for user: {username}")
    else:
        print(f"Package name not found for user: {username}")

@app.route('/updatetime', methods=['POST'])
def update_time():
    username = request.json.get('username')
    print(f"Received update_time request for user: {username}")
    if username in user_data:
        user_data[username]['last_update'] = str(datetime.now())
        print(f"Time updated for user: {username} with time {user_data[username]['last_update']}")
        return jsonify({"message": f"Time updated for user: {username}"}), 200
    else:
        print(f"User '{username}' not found")
        return jsonify({"error": f"User '{username}' not found"}), 404

@app.route('/adduser', methods=['POST'])
def add_user():
    username = request.json.get('username')
    packagename = request.json.get('packagename')
    game_id = request.json.get('game_id')
    is_ps = request.json.get('is_ps')
    ps = request.json.get("private_link")
    wb = request.json.get("webhook")
    
    if not username or not packagename or not game_id:
        print("Missing required fields: username, packagename, and game_id are required")
        return jsonify({"error": "Username, packagename, and game_id are required"}), 400
    
    if username in user_data:
        print(f"User '{username}' already exists")
        return jsonify({"error": f"User '{username}' already exists"}), 409
    
    user_data[username] = {
        'packagename': packagename,
        'game_id': game_id,
        'ps_link': ps,
        'is_ps': is_ps,
        'webhook': wb,
        'cc': 0,
        'last_update': str(datetime.now())
    }
    print(f"User added: {username}")
    send_webhook(wb, f"New user added: ||{username}||")
    return jsonify({"message": f"User '{username}' added successfully"}), 201

@app.route('/rejoinroblox', methods=['POST'])
def rejoin_roblox():
    try:
        username = request.json.get('username')
        if not username:
            return jsonify({"error": "Username is required"}), 400

        print(f"Received rejoinroblox request for user: {username}")

        user_info = user_data.get(username)
        if not user_info:
            return jsonify({"error": f"User '{username}' not found"}), 404

        if user_info.get('is_ps'):
            launch_roblox_with_private_server(user_info['ps_link'], username)
        else:
            launch_roblox(user_info['game_id'], username)

        send_webhook(user_info['webhook'], f"User ||{username}|| has requested to rejoin")
        return jsonify({"message": f"Rejoined Roblox game for user: {username}"}), 200

    except Exception as e:
        print(f"Error occurred while processing rejoin request: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/launchroblox', methods=['POST'])
def launch_roblox_by_packagename():
    try:
        data = request.json
        private_server_link = data.get('private_server_link')
        packagename = data.get('packagename')

        if not private_server_link:
            return jsonify({"error": "Private server link is required"}), 400
        if not packagename:
            return jsonify({"error": "Package name is required"}), 400

        pid = get_pid(packagename)
        if pid:
            close_cmd = f"su -c 'kill {pid}'"
            os.system(close_cmd)
            time.sleep(5)

        launch_cmd = f"am start -a android.intent.action.VIEW -d '{private_server_link}' {packagename}"
        os.system(launch_cmd)

        print(f"Launched Roblox game with ps: {private_server_link} for package: {packagename}")
        return jsonify({"message": f"Launched Roblox game with ps: {private_server_link} for package: {packagename}"}), 200

    except Exception as e:
        print(f"Error launching Roblox game: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/userdata', methods=['GET'])
def get_user_data():
    return jsonify(user_data), 200

@app.route('/close', methods=['POST'])
def close():
    try:
        username = request.json.get('username')
        if not username:
            return jsonify({"error": "Username is required"}), 400

        packagename = user_data.get(username, {}).get('packagename')
        if not packagename:
            return jsonify({"error": "Packagename not found for the given username"}), 404

        pid = get_pid(packagename)
        if not pid:
            return jsonify({"error": f"No process found for package name {packagename}"}), 404

        close_command = f"su -c 'kill {pid}'"
        os.system(close_command)

        return jsonify({"message": f"Process for package {packagename} with PID {pid} has been terminated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/removeuser', methods=['POST'])
def remove_user():
    username = request.json.get('username')
    print(f"Received request to remove user: {username}")
    
    if not username:
        print("No username provided in the request")
        return jsonify({"error": "Username is required"}), 400

    if username in user_data:
        del user_data[username]
        print(f"User '{username}' removed successfully")
        return jsonify({"message": f"User '{username}' removed successfully"}), 200
    else:
        print(f"User '{username}' not found")
        return jsonify({"error": f"User '{username}' not found"}), 404

def check_inactive_users():
    print("Starting check_inactive_users thread...")
    while True:
        time.sleep(60)  
        now = datetime.now()
        inactive_users = []
        for username, data in user_data.items():
            last_update = datetime.strptime(data['last_update'], '%Y-%m-%d %H:%M:%S.%f')
            if now - last_update > timedelta(minutes=5):
                print(f"User Inactive: '{username}'")
                inactive_users.append(username)
        
        for user in inactive_users:
            time.sleep(10)
            print(f"User {user} has been inactive for more than 5 minutes")
            if user_data[user]['is_ps'] == True :
                launch_roblox_with_private_server(user_data[user]['ps_link'], user)
            else:
                launch_roblox(user_data[user]['game_id'], user)

            user_data[user]['last_update'] = str(datetime.now())
            send_webhook(user_data[user]['webhook'],f"User ||{user}|| has been inactive, {user_data[username]['last_update']}")
        print("Inactive users checked.")



thread = threading.Thread(target=check_inactive_users, daemon=True)
thread.start()
print("Background thread started.")

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=6969)
