# Cerevyn Geo-Fencing Attendance System (Flask)

Smart attendance + live location tracking using browser geolocation and a configurable geo-fence.

## Features

- User auth (first user = **Admin**, others = **Employees**)
- Geo-fence based attendance:
  - Check-in / Check-out only when **inside** the configured radius
  - Distance computed using Haversine formula
- Live tracking:
  - Employee can start **Live Tracking**
  - System logs GPS points and whether they are inside/outside the fence
- Admin dashboard:
  - Map view of the geo-fence
  - User list + quick link to **movement map**
  - Latest attendance table
- Admin geo-fence config:
  - Set center lat/lng + radius
  - Click on map to auto-fill lat/lng
- Movement history:
  - Per-user **movement map** with route polyline for a selected date
- Clean, responsive UI using **Bootstrap 5** + **Leaflet** + **OpenStreetMap**

## How to run

1. Create virtual environment
```bash
python -m venv venv
```

```bash
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

2. Install dependencies
```bash

pip install -r requirements.txt
```
# 3. Initialize database + default geo-fence
```bash

flask --app app.py init-db
```
# 4. Run dev server
```bash

python app.py
```

Then open: http://127.0.0.1:5000/

> **Important:** When you first open the app, go to **Register** and create the first user.
> That account becomes **Admin** automatically.


![Dashboard Screenshot](https://github.com/Vamsi8041/Cerevyn-Assignment/blob/7b13e64f6d1d2b2ec4bc9b9697dc5ddbc3a1aad3/photos/Screenshot%202025-11-16%20221853.png)

![Dashboard Screenshot](https://github.com/Vamsi8041/Cerevyn-Assignment/blob/d1443109dae68a08dac0c6f07093c89e15744e64/photos/Screenshot%202025-11-16%20221943.png)

![Dashboard Screenshot](https://github.com/Vamsi8041/Cerevyn-Assignment/blob/d1443109dae68a08dac0c6f07093c89e15744e64/photos/Screenshot%202025-11-16%20221930.png)




## Demo Flow

1. **Admin**
   - Register first → becomes admin
   - Configure geo-fence (Admin → Geo-Fence menu)
   - Optionally create some test employee accounts

2. **Employee**
   - Login as employee
   - Go to **My Attendance**
   - Allow **location** in your browser
   - Use **Check-In / Check-Out** buttons
   - Click **Start Live Tracking** to send movement pings

3. **Admin**
   - Open **Admin Dashboard**
   - View:
     - Geo-fence map
     - Latest attendance events
   - Open **View map** for a user to see their movement path for a selected day.

## Notes

- For demo, we use **SQLite** (`geofence_attendance.db`) in the project folder.
- All times are stored in **UTC**.
- Geo-fence default center is set to Hyderabad – you can change it from the UI.
