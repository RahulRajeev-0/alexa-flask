from flask import Flask, render_template, request, redirect
import os
import pyrebase
from dotenv import load_dotenv

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

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get("email-field")
        password = request.form.get("password")
        # state = request.form.get("state")

        try:
            # Authenticate user using Pyrebase
            user = auth.sign_in_with_email_and_password(email, password)
            print('User signed in:', user['localId'])

            # You can now use this `user['idToken']` for subsequent authenticated requests
            return redirect('/')
        except Exception as e:
            print('Error: ******', e)
            return render_template("index.html", message="Invalid username or password")
    
    return render_template('index.html')



if __name__ == '__main__':
    app.run(debug=True)
