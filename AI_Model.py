import cv2
import os
import time
import atexit
import threading
from deepface import DeepFace
from flask import Flask, render_template, Response
import tkinter as tk
from tkinter import messagebox

app = Flask(__name__)

db_path = r"E:\SUT\SUT Second year\Semester Two\Artificial Intelligence\ai project new\ai project new\person"
RECOGNITION_THRESHOLD = 0.35  
    
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

latest_analysis = []
lock = threading.Lock()
should_exit = threading.Event()

unknown_start_time = None
unknown_detected = False
screenshot_count = 0
person_folder = ""
capturing_screenshots = False
last_person_name = None
last_screenshot_time = 0
name_entered = False
last_analysis_time = 0
text_field_triggered = False  

@atexit.register
def cleanup():
    print("Releasing camera...")
    if cap.isOpened():
        cap.release()
    cv2.destroyAllWindows()
    print("Camera released.")

def get_person_name():
    global person_folder, capturing_screenshots, name_entered, text_field_triggered
    root = tk.Tk()
    root.title("Enter Name")
    root.geometry("300x150")
    root.configure(bg="#f0f0f0")

    label = tk.Label(root, text="Please enter your name:", bg="#f0f0f0", font=("Arial", 12))
    label.pack(pady=10)

    name_var = tk.StringVar()
    entry = tk.Entry(root, textvariable=name_var, font=("Arial", 12), width=20)
    entry.pack(pady=10)

    def submit_name():
        global person_folder, capturing_screenshots, name_entered, text_field_triggered
        name = name_var.get().strip()
        if name:
            person_folder = os.path.join(db_path, name)
            os.makedirs(person_folder, exist_ok=True)
            capturing_screenshots = True
            name_entered = True
            text_field_triggered = False
            root.destroy()
        else:
            messagebox.showwarning("Invalid Input", "Please enter a valid name.")

    submit_button = tk.Button(root, text="Submit", command=submit_name, bg="#4CAF50", fg="white", font=("Arial", 12))
    submit_button.pack(pady=10)

    root.protocol("WM_DELETE_WINDOW", lambda: root.destroy())
    root.mainloop()

def analyze_faces():
    global unknown_start_time, unknown_detected, screenshot_count, person_folder
    global capturing_screenshots, last_person_name, last_screenshot_time, name_entered
    global last_analysis_time, text_field_triggered

    while not should_exit.is_set():
        if not cap.isOpened():
            print("Camera not available.")
            time.sleep(1)
            continue

        ret, frame = cap.read()
        if not ret:
            continue

        current_time = time.time()

        if capturing_screenshots and name_entered:
            if current_time - last_screenshot_time >= 0.5: 
                if last_person_name and last_person_name != "Unknown":
                    pass 
                else:
                    screenshot_path = os.path.join(person_folder, f"{os.path.basename(person_folder)}_{screenshot_count + 1}.jpg")
                    cv2.imwrite(screenshot_path, frame)
                    screenshot_count += 1
                    print(f"Saved screenshot {screenshot_count} for {os.path.basename(person_folder)}")
                    last_screenshot_time = current_time

                if screenshot_count >= 10:
                    capturing_screenshots = False
                    screenshot_count = 0
                    person_folder = ""
                    name_entered = False
                    last_person_name = None
                    text_field_triggered = False
                    print("Finished capturing screenshots.")
            continue  

        if current_time - last_analysis_time < 1.5:
            if unknown_detected and not text_field_triggered and not name_entered:
                if current_time - unknown_start_time >= 15:
                    get_person_name()
                    text_field_triggered = True
                    unknown_detected = False
                    unknown_start_time = None
            time.sleep(0.1)
            continue

        try:
            results = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)

            if isinstance(results, dict):
                results = [results]

            updated_results = []
            for face in results:
                region = face['region']
                x, y, w, h = region['x'], region['y'], region['w'], region['h']
                face_img = frame[y:y + h, x:x + w]
                person_name = "Unknown"
                dominant_emotion = face['dominant_emotion']

                if not name_entered:  
                    try:
                        verify_df = DeepFace.find(
                            face_img,
                            db_path=db_path,
                            model_name="Facenet",
                            enforce_detection=False,
                            silent=True
                        )

                        if len(verify_df) > 0 and len(verify_df[0]) > 0:
                            top_match = verify_df[0].iloc[0]
                            distance = top_match['distance']
                            identity_path = top_match['identity']
                            matched_name = os.path.basename(os.path.dirname(identity_path))

                            if distance < RECOGNITION_THRESHOLD:
                                person_name = matched_name
                            print(f"Top match: {matched_name}, Distance: {distance:.3f}")

                    except Exception as e:
                        print("Recognition error:", e)

                updated_results.append({
                    "box": (x, y, w, h),
                    "name": person_name,
                    "emotion": dominant_emotion
                })

            with lock:
                global latest_analysis
                latest_analysis = updated_results

            if updated_results and not capturing_screenshots:
                current_person = updated_results[0]["name"]
                last_person_name = current_person
                if current_person == "Unknown" and not text_field_triggered:
                    if not unknown_detected:
                        unknown_detected = True
                        unknown_start_time = current_time
                    elif current_time - unknown_start_time >= 10 and not name_entered:
                        get_person_name()
                        text_field_triggered = True
                        unknown_detected = False
                        unknown_start_time = None
                else:
                    unknown_detected = False
                    unknown_start_time = None
                    text_field_triggered = False

            last_analysis_time = current_time

        except Exception as e:
            print("Analysis error:", e)

def generate_frames():
    global capturing_screenshots, last_person_name
    while not should_exit.is_set():
        if not cap.isOpened():
            break

        ret, frame = cap.read()
        if not ret:
            break

        with lock:
            faces = latest_analysis.copy()

        for face in faces:
            x, y, w, h = face["box"]
            label = f"{face['name']} is {face['emotion']}"

            c
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(frame, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        if capturing_screenshots and last_person_name and last_person_name != "Unknown":
            cv2.putText(frame, "Please wait 5 seconds", (30, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3, cv2.LINE_AA)

        cv2.imshow("Live Feed - Press Q to Quit", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("Q pressed. Exiting...")
            should_exit.set()
            break

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.03)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video')
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_flask():
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    threading.Thread(target=analyze_faces, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()

    try:
        while not should_exit.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Keyboard interrupt. Exiting...")
        should_exit.set()