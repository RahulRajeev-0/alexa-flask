
from flask import Flask, render_template, request, redirect, jsonify
import os
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



# function for generating code 
def generate_authorization_code(uid):
    """
    Generates a JWT authorization code that encodes the user's UID 
    """
    try:
        # Define the payload with uid only
        payload = {
            'uid': uid
        }
        # Encode the payload using the secret key and return the JWT token as the authorization code
        authorization_code = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        # Store the authorization code in the database
        db.child('new_db').child('users').child(uid).child('alexa').update({"authorization_code": authorization_code})

        return authorization_code
    except Exception as e:
        print('Error:', e)
        return None


def decode_authorization_code(authorization_code):
    """
    Decodes the JWT authorization code to retrieve the UID.
    """
    try:
        # Decode the JWT token using the secret key
        payload = jwt.decode(authorization_code, SECRET_KEY, algorithms=['HS256'])
        # Extract the uid from the payload
        uid = payload['uid']
        return uid
    except jwt.InvalidTokenError:
        print("Invalid authorization code")
        return None



ACCESS_TOKEN_EXPIRES = timedelta(minutes=60) 
REFRESH_TOKEN_EXPIRES = timedelta(days=360)


def generate_jwt_token(identity, token_type, expires_in, uid):
    """
    Generates JWT token with an expiration time.
    token_type: "access" or "refresh"
    """
    now = datetime.now()
    exp = now + expires_in
    payload = {
        'sub': identity,
        'iat': now,
        'exp': exp,
        'type': token_type,
        'uid':uid
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    if token_type == "access":
        db.child("new_db").child("users").child(uid).child("alexa").update({"access_token": token})
    elif token_type == 'refresh':
        db.child("new_db").child("users").child(uid).child("alexa").update({"refresh_token": token})
    return token


def verify_jwt_token(token, token_type):
    """
    Verifies and decodes JWT token.
    token_type: "access" or "refresh"
    """
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        if decoded_token.get('type') == token_type:
            return decoded_token['sub']
        return None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


@app.route('/access-token', methods=['POST'])
def access_token():
    """
    Handles access token generation either during login or refresh process.
    """
    code = request.json.get("code")
    refresh_token = request.json.get("refresh_token")

    if refresh_token:
        # If refresh token is present, generate new access token
        user_id = verify_jwt_token(refresh_token, 'refresh')
        if user_id:
            new_access_token = generate_jwt_token(user_id, 'access', ACCESS_TOKEN_EXPIRES)
            return jsonify({"access_token": new_access_token, "token_type": "bearer", "expires_in": 3600}), 200
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    elif code:
        # Generate new access and refresh token based on authorization code
        user_id = decode_authorization_code(code)
        if user_id:
            access_token = generate_jwt_token(user_id, 'access', ACCESS_TOKEN_EXPIRES)
            refresh_token = generate_jwt_token(user_id, 'refresh', REFRESH_TOKEN_EXPIRES)
            return jsonify({"access_token": access_token, "token_type": "bearer", "expires_in": 3600, "refresh_token": refresh_token}), 200
        return jsonify({"error": "Invalid authorization code"}), 401

    return jsonify({"error": "Missing code or refresh_token"}), 400



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
            print("&&&&&&&&&&&&&&&&&&&&&")
            print(db.child('new_db').child('users').child(uid).get().val())

            authorization_code = generate_authorization_code(uid)
            redirect_url = 'https://layla.amazon.com/api/skill/link/M28J7ZKDG13G8U'
            # below is the actual code that is need for production
            redirect_uri_final = f"{redirect_url}?state={state}&code={authorization_code}"
            # print('working successfully ******')
            return redirect(redirect_uri_final)
        except Exception as e:
            # print('Error: ******', e)
            return render_template("index.html", message="Invalid username or password")
    
    return render_template('index.html')



# ---------------------------------------- device discovery ------------------------------------------
@app.route('/get_device_details', methods=['GET'])
def get_device_details(request):
    authorization_header = request.META.get('HTTP_AUTHORIZATION')
    if authorization_header and authorization_header.startswith('Bearer '):
        access_token_get = authorization_header[len('Bearer '):]
        decoded_token = jwt.decode(access_token_get, SECRET_KEY, algorithms=['HS256'])
        uid = decoded_token['uid']
        user = db.child('new_db').child('users').child(uid).get().val()

        if not user:
            return jsonify({"error": "No user data found"}, status=404)

        
        alexa_tokens = user.get("alexa", {})
        if alexa_tokens.get("access_token") == access_token_get:
            device_id = []
            user_homes = user.get("homes", {})
            process_homes(user_homes, device_id)

            guest_data = db.child("new_db").child("users").child(uid).child("homes").child("access").get().val()
            if guest_data:
                for guest_home_id, access_info in guest_data.items():
                    owner_uid = access_info.get("owner_id")
                    if owner_uid:
                        owner_home_data = db.child("new_db").child("users").child(owner_uid).child("homes").child(guest_home_id).get().val()
                        if owner_home_data:
                            process_homes({guest_home_id: owner_home_data}, device_id)

            dev_product_id = [i["id"] + "_" + i["product_id"] for i in device_id]
            product_name = [i["name"] for i in device_id]

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
                            "id": device_key,
                            "name": device_data.get("name"),
                            "product_id": product_id
                        })
    except Exception as e:
        print("Error:", e)

if __name__ == '__main__':
    app.run(debug=True)
