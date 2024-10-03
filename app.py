
from flask import Flask, render_template, request, redirect, jsonify
import os
import string
import secrets
import pyrebase
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
# Load environment variables
load_dotenv()

app = Flask(__name__)

# Firebase configuration for Pyrebase (replace with your own config values)
firebase_config = {
    "apiKey": os.getenv('FIREBASE_API_KEY'),
    "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN'),
    "databaseURL": os.getenv('DATABASE_URL'),
    "projectId": os.getenv('FIREBASE_PROJECT_ID'),
    "storageBucket": os.getenv('FIREBASE_STORAGE_BUCKET'),
    "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID'),
    "appId": os.getenv('FIREBASE_APP_ID'),
    "measurementId": os.getenv('FIREBASE_MEASUREMENT_ID')
}

# Initialize Pyrebase
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()
db = firebase.database()
SECRET_KEY = os.getenv('SECRET_KEY')




def generate_authorization_code(uid):
    '''
    generate a random url safe string 
    also save the generated code in the db of the user inside alexa node 
    '''
    characters = string.ascii_letters + string.digits
    authorization_code = ''.join(secrets.choice(characters) for _ in range(16))
    try:
        db.child("new_db").child("users").child(uid).child("alexa").update({"authorization_code": authorization_code})
    except Exception as e:
        pass
    return authorization_code

def refresh_access_token(code):
    users_data = db.child("new_db").child("users").get().val()
    if not users_data:
        return "None"

    try:
        for uid, user_data in users_data.items():
            alexa_data = user_data.get("alexa", {})
            if alexa_data.get("authorization_code") == code:
                access_token_prefix = "Atzr1|"
                characters = string.ascii_letters + string.digits
                random_part = ''.join(secrets.choice(characters) for _ in range(32))
                refresh_token = access_token_prefix + random_part
                db.child("new_db").child("users").child(uid).child("alexa").update({"refresh_token": refresh_token})
                return refresh_token

    except Exception as e:
        print(f"Error generating refresh token: {e}")
        return "None"

    return "None"


def refresh_token_to_refresh(existing_refresh_token):
    users_data = db.child("new_db").child("users").get().val()
    if not users_data:
        return "None"

    try:
        for uid, user_data in users_data.items():
            alexa_data = user_data.get("alexa", {})
            if alexa_data.get("refresh_token") == existing_refresh_token:
                access_token_prefix = "Atzr1|"
                characters = string.ascii_letters + string.digits
                new_refresh_token = ''.join(secrets.choice(characters) for _ in range(32))
                db.child("new_db").child("users").child(uid).child("alexa").update({"refresh_token": new_refresh_token})
                return new_refresh_token

    except Exception as e:
        print(f"Error generating new refresh token: {e}")
        return "None"

    return "None"



def generate_access_token_login(refresh_token):
    users_data = db.child("new_db").child("users").get().val()
    if not users_data:
        return "None"

    try:
        for uid, user_data in users_data.items():
            alexa_data = user_data.get("alexa", {})
            if alexa_data.get("refresh_token") == refresh_token:
                access_token_prefix = "Atza1|"
                characters = string.ascii_letters + string.digits
                random_part = ''.join(secrets.choice(characters) for _ in range(32))
                access_token = access_token_prefix + random_part
                db.child("new_db").child("users").child(uid).child("alexa").update({"access_token": access_token})
                return access_token

    except Exception as e:
        print(f"Error generating access token with refresh token: {e}")
        return "None"

    return "None"


def generate_access_token(code):
    '''
    generating acceess token based on the authorization code 
    '''
    users_data = db.child("new_db").child("users").get().val()
    if not users_data:
        return "None"

    try:
        for uid, user_data in users_data.items():
            alexa_data = user_data.get("alexa", {})
            if alexa_data.get("authorization_code") == code:

                # using the access token prefix to validate our access tokens 
                # every access token is having the same prefix 
                access_token_prefix = "Atza1|"
                characters = string.ascii_letters + string.digits
                random_part = ''.join(secrets.choice(characters) for _ in range(32))
                access_token = access_token_prefix + random_part
                db.child("new_db").child("users").child(uid).child("alexa").update({"access_token": access_token})
                return access_token

    except Exception as e:
        print(f"Error generating access token: {e}")
        return "None"

    return "None"



@app.route('/access-token', methods=['POST'])
def access_token():
    '''
    access token is generated on two situations , 
    in the login time , when there is no refresh token to generate access token 
    after that when the access token expires to get new one (in that time the refresh token is present)
    '''
    try:
        if request.method == 'POST':
            print("\n***********************\n")
            print("Login is successfull and access token url is called 🪲")
        
            code = request.form.get("code") or (request.json.get("code") if request.is_json else None)
            refresh_token = request.form.get("refresh_token") or (request.json.get("refresh_token") if request.is_json else None)

            if refresh_token is not None:
                # generating new access token if the refresh token is present
                new_access_token = generate_access_token_login(refresh_token)
                # generating new refreash token for the access token 
                new_refresh_token = refresh_token_to_refresh(refresh_token)
                return jsonify({"access_token": new_access_token, "token_type": "bearer", "expires_in": 86400, "refresh_token": new_refresh_token})

            elif code is not None:
                # if the refreash token is not present but the code is present 
                # then generates a new access and refresh token 
                access_token = generate_access_token(code)
                refresh_token = refresh_access_token(code)
                return jsonify({"access_token": access_token, "token_type": "bearer", "expires_in": 86400, "refresh_token": refresh_token})
            else:
                return jsonify({"error": "Missing code or refresh_token"}, status=400)
        else:
            return jsonify({"error": "Unsupported request method"}, status=405)
    except Exception as e:
        print(" \n Error happended in the access token genereation \n", e)



# before deploying the project need the add the redirect url properly 
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get("email-field")
        password = request.form.get("password")
        state = request.form.get("state")

        try:
            # Authenticate user using Pyrebase
            user = auth.sign_in_with_email_and_password(email, password)
            uid = user['localId']
           
            print(db.child('new_db').child('users').child(uid).get().val())

            authorization_code = generate_authorization_code(uid)
            redirect_url = 'https://layla.amazon.com/api/skill/link/M28J7ZKDG13G8U'
            # below is the actual code that is need for production
            redirect_uri_final = f"{redirect_url}?state={state}&code={authorization_code}"
            
            return redirect(redirect_uri_final)
        except Exception as e:
            print('Error: ******', e)
            return render_template("index.html", message="Invalid username or password")
    state = request.args.get('state')
    return render_template('index.html',  state=state)



# ---------------------------------------- device discovery ------------------------------------------
@app.route('/get_device_details', methods=['GET'])
def get_device_details(request):
    authorization_header = request.META.get('HTTP_AUTHORIZATION')
    if authorization_header and authorization_header.startswith('Bearer '):
        access_token_get = authorization_header[len('Bearer '):]
        all_users_data = db.child("new_db").child("users").get().val()

        if not all_users_data:
            return jsonify({"error": "No user data found"}, status=404)

        for uid, user_data in all_users_data.items():
            alexa_tokens = user_data.get("alexa", {})
            # comparing the access token 
            if alexa_tokens.get("access_token") == access_token_get:
                device_id = []
                user_homes = user_data.get("homes", {})
                process_homes(user_homes, device_id)

                guest_data = db.child("new_db").child("users").child(uid).child("homes").child("access").get().val()

                # getting the devices of other user how gave you access , for that we need to get the user uid from acess node data
                # after getting the uid we fatch the product_id of that perticular user products 
                if guest_data:
                    for guest_home_id, access_info in guest_data.items():
                        owner_uid = access_info.get("owner_id")
                        if owner_uid:
                            owner_home_data = db.child("new_db").child("users").child(owner_uid).child("homes").child(guest_home_id).get().val()
                            if owner_home_data:
                                process_homes({guest_home_id: owner_home_data}, device_id)

                dev_product_id = [i["id"] + "_" + i["product_id"] for i in device_id]
                product_name = [i["name"] for i in device_id]

                # example 
                # dev_product_id = ["device1_3ch1frb214", "device2_3ch1frb214"]
                # product_name = ["TestLight1",]
                return jsonify({"name": product_name, "device_id": dev_product_id})

    return jsonify({"error": "Unauthorized"}, status=401)

def process_homes(homes_data, device_id):
    try:
        for home_id, home_data in homes_data.items():
            rooms = home_data.get("rooms", {})
            for room_id, room_data in rooms.items():
                products = room_data.get("products", {})
                for product_id, product_data in products.items():
                    devices = product_data.get("devices", {})
                    for device_key, device_data in devices.items():
                        device_id.append({
                            "id": device_key,  # device key will be device 1 then device2
                            "name": device_data.get("name"),
                            "product_id": product_id
                        })
    except Exception as e:
        print("Error:", e)


if __name__ == '__main__':
    app.run(debug=True)
