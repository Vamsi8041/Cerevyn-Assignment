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

```bash
# 1. Create virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize database + default geo-fence
flask --app app.py init-db

# 4. Run dev server
flask --app app.py run
# Or:
python app.py
```

Then open: http://127.0.0.1:5000/

> **Important:** When you first open the app, go to **Register** and create the first user.
> That account becomes **Admin** automatically.

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

You can now extend this base:
- Add CSV export for attendance logs
- Add email/SMS alerts when user moves out of fence
- Integrate with your HRMS or payroll
