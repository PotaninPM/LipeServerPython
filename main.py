from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from models import User, Points, GroupModel, Request
from pydantic import BaseModel
import firebase_admin
import asyncio
import threading
from firebase_admin import credentials, db, messaging
import math

#1
app = FastAPI()

cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'link to db'
})

ref_users = db.reference('users')
ref_rating = db.reference('rating')

def update_rating(event=None):
    try:
        users_snapshot = ref_rating.get()
        print("Fetched data from Firebase:", users_snapshot)

        if isinstance(users_snapshot, list):
            users_list = [
                {
                    'place': index,
                    'points': user_data['points'],
                    'userUid': user_data['userUid']
                }
                for index, user_data in enumerate(users_snapshot)
                if user_data is not None and 'userUid' in user_data
            ]

            sorted_users = sorted(users_list, key=lambda x: x['points'], reverse=True)

            updated_data = {}
            for index, user in enumerate(sorted_users):
                new_place = index + 1
                updated_data[str(new_place)] = {
                    'place': new_place,
                    'points': user['points'],
                    'userUid': user['userUid']
                }
                
                ref_users.child(user['userUid']).update({'place_in_rating': new_place})
        
            ref_rating.set(updated_data)

            print("Rating updated successfully")
        else:
            print("No data found")

    except Exception as e:
        print(f"Error updating rating: {str(e)}")

@app.get("/")
async def read_root():
    return {"message": "Hello World!"}

def distance_between_coordinates(lat1, lon1, lat2, lon2):
    R = 6371.0 

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return distance

def send_notification_to_user(device_token: str, title: str, message: str, type: str):
    try:
        message = messaging.Message(
            data={
                "title": title,
                "message": message,
                "type": type
            },
            token=device_token
        )
        response = messaging.send(message)
        print(f"Sent message: {response}")
    except Exception as e:
        print(f"Failed to send message to {device_token}: {str(e)}")

@app.post("/query_to_friend")
async def query_to_friend(request: FastAPIRequest):
    data = await request.json()
    req = Request(**data)

    sender = req.senderUid
    receiver = req.receiverUid

    ref_user = db.reference("users")

    try:
        receiver_snapshot = ref_user.child(receiver).get()
        sender_snapshot = ref_user.child(sender).child("firstAndLastName")

        if receiver_snapshot and sender_snapshot:
            receiver_token = receiver_snapshot.get("userToken", "")
            sender_name = sender_snapshot.get("")
            send_notification_to_user(receiver_token, "Новая заявка в друзья!", f"Вам пришла заявка от {sender_name}", "friendship_request")
            return {"status": "Notification sent"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class EventLocation(BaseModel):
    latitude: float
    longitude: float

@app.post("/create_event")
async def create_ent_event(event: EventLocation):
    try:
        users_ref = db.reference("users")
        users_snapshot = users_ref.get()
        notified_users = []
        if users_snapshot:
            for user_key, user_data in users_snapshot.items():
                user_token = user_data.get("userToken")
                if user_token:
                    loc_db_ref = db.reference(f"location/{user_key}")
                    location_snapshot = loc_db_ref.get()
                    if location_snapshot:
                        user_lat = float(location_snapshot.get("latitude"))
                        user_lon = float(location_snapshot.get("longitude"))
                        if user_lat is not None and user_lon is not None:
                            distance = distance_between_coordinates(user_lat, user_lon, event.latitude, event.longitude)
                            if distance < 10.0:
                                if(distance < 1.0):
                                    message = f"В {distance * 1000} метрах от вас создано новое событие!"
                                    print(f"Sending notification to user {user_key} with token {user_token}")
                                    send_notification_to_user(user_token, "Новое событие!", message, "new_event")
                                    notified_users.append(user_key)
                                else:
                                    message = f"В {distance:.2f} километрах от вас создано новое событие!"
                                    print(f"Sending notification to user {user_key} with token {user_token}")
                                    send_notification_to_user(user_token, "Новое событие!", message, "new_event")
                                    notified_users.append(user_key)

        return {"status": "Event created", "notified_users": notified_users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating event: {str(e)}")

@app.post("/accept_query_to_friend")
async def accept_query_to_friend(request: FastAPIRequest):
    data = await request.json()
    req = Request(**data)

    sender = req.senderUid
    receiver = req.receiverUid

    ref_user = db.reference("users")

    try:
        sender_token_snapshot = ref_user.child(sender).child("userToken").get()
        receiver_name_snapshot = ref_user.child(receiver).child("firstAndLastName").get()

        if sender_token_snapshot and receiver_name_snapshot:
            sender_token = sender_token_snapshot
            receiver_name = receiver_name_snapshot
            send_notification_to_user(sender_token, "Заявка в друзья принята!", f"{receiver_name} принял вашу заявку в друзья", "accept_friendship")
            return {"status": "Notification sent"}
        else:
            raise HTTPException(status_code=404, detail="User not found or incomplete data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/get_points")
async def get_points(points: Points):
    try:
        selected_users = points.people
        points_int = points.points
        ref_users = db.reference("users")
        ref_rating = db.reference("rating")

        for user_uid in selected_users:
            user_points_ref = ref_users.child(user_uid).child("points")
            current_points = user_points_ref.get() or 0
            new_points = current_points + points_int
            user_points_ref.set(new_points)

            user_data = ref_users.child(user_uid).get()
            if user_data and "userToken" in user_data:
                notification_token = user_data["userToken"]
                send_notification_to_user(
                    notification_token,
                    "Новые баллы начислены",
                    f"Вам начислены баллы, ваш новый рейтинг: {new_points}",
                    "rating_update"
                )

        return {"status": "Points awarded"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error awarding points: {str(e)}")

    
ref_rating.listen(update_rating)

# import threading
# threading.Thread(target=update_user_ranking).start()
