"""Route data service for heatmap feature.

Handles fetching, parsing, and caching route points from Garmin activities.
"""
from backend.database import get_db
from backend.garmin_client import GarminClient


class RouteService:
    def __init__(self, tokenstore=None):
        self.garmin = None
        self._tokenstore = tokenstore

    def _ensure_garmin(self):
        if not self.garmin:
            self.garmin = GarminClient(tokenstore=self._tokenstore)
            login_result = self.garmin.login('', '')
            if not login_result.get('success'):
                raise RuntimeError('需要先同步登录一次以保存 Token')

    def fetch_and_store_route(self, activity_id):
        """Fetch route data for an activity and store in database."""
        self._ensure_garmin()

        try:
            # First try GPX download (most reliable for GPS data)
            points = self.garmin.fetch_activity_gpx(activity_id)

            # If GPX fails, try extracting from detail metrics
            if not points:
                detail = self.garmin.fetch_activity_details(activity_id)
                if detail:
                    points = self._extract_points(detail)

            if not points:
                return None

            db = get_db()
            try:
                # Clear existing points for this activity
                db.execute("DELETE FROM activity_route_points WHERE activity_id=?", (activity_id,))

                # Store points
                for i, point in enumerate(points):
                    db.execute("""
                        INSERT INTO activity_route_points
                        (activity_id, point_index, latitude, longitude, distance_m,
                         elapsed_s, speed_mps, heart_rate, altitude_m, recorded_at, city, district)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        activity_id, i,
                        point.get('lat'), point.get('lng'),
                        point.get('distance'), point.get('elapsed'),
                        point.get('speed'), point.get('hr'),
                        point.get('altitude'), point.get('time'),
                        point.get('city'), point.get('district')
                    ))

                # Generate and store summary
                self._store_summary(db, activity_id, points)
                db.commit()
                return len(points)
            finally:
                db.close()
        except Exception as e:
            print(f"Error fetching route for activity {activity_id}: {e}")
            return None

    def _extract_points(self, detail):
        """Extract coordinate points from activity detail data."""
        points = []

        # Try to extract from metrics (activityDetailMetrics)
        metrics = detail.get('metrics', {})
        if isinstance(metrics, dict):
            metric_list = metrics.get('activityDetailMetrics', [])
            if isinstance(metric_list, list):
                for m in metric_list:
                    lat = m.get('latitude') or m.get('lat')
                    lng = m.get('longitude') or m.get('lng') or m.get('lon')
                    if lat and lng:
                        points.append({
                            'lat': float(lat),
                            'lng': float(lng),
                            'distance': m.get('distance') or m.get('sumDistance'),
                            'elapsed': m.get('elapsedDuration') or m.get('timerDuration'),
                            'speed': m.get('speed') or m.get('movingSpeed'),
                            'hr': m.get('heartRate') or m.get('averageHR'),
                            'altitude': m.get('elevation') or m.get('altitude'),
                            'time': m.get('startTimeGMT') or m.get('timestamp'),
                        })

        # Try to extract from summary if it has polyline
        summary = detail.get('summary', {})
        if isinstance(summary, dict):
            # Check for polyline
            polyline = summary.get('polyline') or summary.get('activityPolyline')
            if polyline and isinstance(polyline, str):
                decoded = self._decode_polyline(polyline)
                points.extend(decoded)

            # Check for direct coordinate lists
            coords = summary.get('coordinates') or summary.get('latLngPoints')
            if coords and isinstance(coords, list):
                for c in coords:
                    if isinstance(c, (list, tuple)) and len(c) >= 2:
                        points.append({'lat': float(c[0]), 'lng': float(c[1])})
                    elif isinstance(c, dict):
                        lat = c.get('lat') or c.get('latitude')
                        lng = c.get('lng') or c.get('lon') or c.get('longitude')
                        if lat and lng:
                            points.append({'lat': float(lat), 'lng': float(lng)})

        return points

    def _decode_polyline(self, polyline, precision=5):
        """Decode a polyline string to coordinate list."""
        points = []
        index = 0
        lat = 0
        lng = 0
        factor = 10 ** precision

        while index < len(polyline):
            # Latitude
            shift = 0
            result = 0
            while True:
                b = ord(polyline[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            lat += ~(result >> 1) if (result & 1) else (result >> 1)

            # Longitude
            shift = 0
            result = 0
            while True:
                b = ord(polyline[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            lng += ~(result >> 1) if (result & 1) else (result >> 1)

            points.append({
                'lat': lat / factor,
                'lng': lng / factor,
            })

        return points

    def _store_summary(self, db, activity_id, points):
        """Store route summary for an activity."""
        if not points:
            return

        lats = [p['lat'] for p in points if p.get('lat')]
        lngs = [p['lng'] for p in points if p.get('lng')]

        if not lats or not lngs:
            return

        center_lat = sum(lats) / len(lats)
        center_lng = sum(lngs) / len(lngs)

        # Simple city detection based on coordinates
        city = self._detect_city(center_lat, center_lng)

        db.execute("""
            INSERT OR REPLACE INTO activity_route_summary
            (activity_id, point_count, min_lat, max_lat, min_lng, max_lng,
             center_lat, center_lng, city, district, distance_m, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
        """, (
            activity_id,
            len(points),
            min(lats), max(lats),
            min(lngs), max(lngs),
            center_lat,
            center_lng,
            city,
            None,
            points[-1].get('distance') if points else None,
        ))

    def _detect_city(self, lat, lng):
        """Simple city detection based on coordinates."""
        # Major cities in China with approximate bounding boxes
        cities = [
            ('上海市', 30.8, 31.9, 120.9, 122.0),
            ('北京市', 39.7, 41.1, 115.4, 117.5),
            ('广州市', 22.5, 23.9, 112.9, 114.1),
            ('深圳市', 22.4, 22.9, 113.7, 114.5),
            ('杭州市', 29.9, 30.6, 119.7, 120.8),
            ('成都市', 30.3, 31.1, 103.6, 104.5),
            ('武汉市', 29.9, 31.4, 113.7, 115.1),
            ('南京市', 31.6, 32.5, 118.2, 119.3),
            ('重庆市', 28.9, 30.5, 105.8, 107.5),
            ('西安市', 34.0, 34.6, 108.5, 109.5),
            ('苏州市', 30.9, 31.9, 119.9, 121.4),
            ('天津市', 38.5, 40.1, 116.5, 118.0),
            ('长沙市', 27.9, 28.6, 112.5, 113.5),
            ('郑州市', 34.3, 35.0, 113.2, 114.3),
            ('青岛市', 35.7, 36.9, 119.8, 121.3),
            ('嘉兴市', 30.5, 30.9, 120.5, 121.0),
            ('宁波市', 29.5, 30.2, 121.0, 122.0),
            ('温州市', 27.5, 28.5, 120.3, 121.3),
            ('合肥市', 31.5, 32.2, 117.0, 117.6),
            ('福州市', 25.8, 26.4, 119.1, 119.6),
            ('厦门市', 24.6, 25.0, 117.8, 118.3),
            ('昆明市', 24.7, 25.4, 102.4, 103.1),
            ('贵阳市', 26.3, 26.9, 106.4, 107.0),
            ('南昌市', 28.5, 29.0, 115.7, 116.1),
            ('济南市', 36.4, 37.0, 116.8, 117.4),
            ('大连市', 38.7, 39.3, 121.4, 122.0),
            ('哈尔滨市', 45.5, 46.1, 126.2, 127.0),
            ('沈阳市', 41.6, 42.1, 123.2, 123.8),
            ('长春市', 43.7, 44.2, 125.1, 125.7),
        ]

        for city_name, min_lat, max_lat, min_lng, max_lng in cities:
            if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                return city_name

        return None

    def backfill_routes(self, limit=50):
        """Backfill route data for activities that don't have it yet."""
        self._ensure_garmin()

        db = get_db()
        # Find activities without route data
        rows = db.execute("""
            SELECT a.id FROM activities a
            LEFT JOIN activity_route_summary s ON s.activity_id = a.id
            WHERE a.type='running' AND s.activity_id IS NULL
            ORDER BY a.start_time DESC LIMIT ?
        """, (limit,)).fetchall()
        db.close()

        filled = 0
        for row in rows:
            result = self.fetch_and_store_route(row['id'])
            if result:
                filled += 1

        # Also update existing summaries without city
        self._update_missing_cities()

        return {'filled': filled, 'total': len(rows)}

    def _update_missing_cities(self):
        """Update route summaries that don't have city information."""
        db = get_db()
        try:
            rows = db.execute("""
                SELECT activity_id, center_lat, center_lng
                FROM activity_route_summary
                WHERE city IS NULL AND center_lat IS NOT NULL
            """).fetchall()

            for row in rows:
                city = self._detect_city(row['center_lat'], row['center_lng'])
                if city:
                    db.execute(
                        "UPDATE activity_route_summary SET city=? WHERE activity_id=?",
                        (city, row['activity_id'])
                    )
            db.commit()
        finally:
            db.close()

    def get_heatmap_data(self, date_from=None, date_to=None, mode='distance', city=None, max_points=50000):
        """Get heatmap data for visualization."""
        db = get_db()

        # Build query
        query = """
            SELECT p.latitude, p.longitude, p.distance_m, p.speed_mps,
                   p.heart_rate, p.altitude_m, a.distance as activity_distance,
                   a.start_time, s.city
            FROM activity_route_points p
            JOIN activities a ON a.id = p.activity_id
            LEFT JOIN activity_route_summary s ON s.activity_id = p.activity_id
            WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
        """
        params = []

        if date_from:
            query += " AND a.start_time >= ?"
            params.append(date_from)
        if date_to:
            query += " AND a.start_time <= ?"
            params.append(date_to + ' 23:59:59')
        if city:
            query += " AND s.city = ?"
            params.append(city)

        query += " ORDER BY a.start_time DESC"

        rows = db.execute(query, params).fetchall()

        # Sample points if too many
        total_points = len(rows)
        if total_points > max_points:
            step = total_points // max_points
            rows = rows[::step]

        # Build points list with weights
        points = []
        for r in rows:
            weight = 0.5  # Base weight for all points
            if mode == 'distance':
                # Higher weight for longer activities
                distance = r['activity_distance'] or 0
                weight = 0.3 + 0.7 * min(1.0, distance / 10000)
            elif mode == 'pace':
                speed = r['speed_mps']
                if speed and speed > 0:
                    # Higher weight for faster pace
                    weight = 0.3 + 0.7 * min(1.0, speed / 4.0)

            points.append({
                'lat': r['latitude'],
                'lng': r['longitude'],
                'weight': round(weight, 2),
            })

        # Get summary stats
        summary = self._get_summary(db, date_from, date_to, city)

        # Get hot routes
        hot_routes = self._get_hot_routes(db, date_from, date_to, city)

        # Get default city and center
        default_city, center, bounds = self._get_default_city(db)

        db.close()

        return {
            'default_city': default_city,
            'center': center,
            'bounds': bounds,
            'summary': summary,
            'points': points,
            'hot_routes': hot_routes,
        }

    def _get_summary(self, db, date_from=None, date_to=None, city=None):
        """Get summary statistics."""
        # First get distinct activities with route data
        activity_query = """
            SELECT DISTINCT a.id, a.distance, a.start_time
            FROM activity_route_points p
            JOIN activities a ON a.id = p.activity_id
            LEFT JOIN activity_route_summary s ON s.activity_id = p.activity_id
            WHERE p.latitude IS NOT NULL
        """
        params = []
        if date_from:
            activity_query += " AND a.start_time >= ?"
            params.append(date_from)
        if date_to:
            activity_query += " AND a.start_time <= ?"
            params.append(date_to + ' 23:59:59')
        if city:
            activity_query += " AND s.city = ?"
            params.append(city)

        activities = db.execute(activity_query, params).fetchall()

        # Calculate summary from distinct activities
        total_distance = sum(a['distance'] or 0 for a in activities)
        latest_activity = max((a['start_time'] or '') for a in activities) if activities else ''

        # Get total points count
        points_query = """
            SELECT COUNT(p.id) as points
            FROM activity_route_points p
            JOIN activities a ON a.id = p.activity_id
            LEFT JOIN activity_route_summary s ON s.activity_id = p.activity_id
            WHERE p.latitude IS NOT NULL
        """
        points_params = []
        if date_from:
            points_query += " AND a.start_time >= ?"
            points_params.append(date_from)
        if date_to:
            points_query += " AND a.start_time <= ?"
            points_params.append(date_to + ' 23:59:59')
        if city:
            points_query += " AND s.city = ?"
            points_params.append(city)

        points_row = db.execute(points_query, points_params).fetchone()

        # Get city count
        city_count = db.execute(
            "SELECT COUNT(DISTINCT city) FROM activity_route_summary WHERE city IS NOT NULL"
        ).fetchone()[0] or 0

        return {
            'cities': city_count,
            'points': points_row['points'] or 0,
            'distance_km': round(total_distance / 1000, 1),
            'latest_activity': latest_activity[:10] if latest_activity else '',
        }

    def _get_hot_routes(self, db, date_from=None, date_to=None, city=None, limit=5):
        """Get hot routes summary."""
        # First get distinct activities per city
        query = """
            SELECT s.city as area,
                   COUNT(DISTINCT a.id) as count,
                   SUM(DISTINCT a.distance) as total_distance,
                   AVG(a.avg_pace) as avg_pace,
                   MAX(a.start_time) as latest_activity
            FROM activity_route_points p
            JOIN activities a ON a.id = p.activity_id
            LEFT JOIN activity_route_summary s ON s.activity_id = p.activity_id
            WHERE s.city IS NOT NULL
        """
        params = []
        if date_from:
            query += " AND a.start_time >= ?"
            params.append(date_from)
        if date_to:
            query += " AND a.start_time <= ?"
            params.append(date_to + ' 23:59:59')
        if city:
            query += " AND s.city = ?"
            params.append(city)

        query += " GROUP BY s.city ORDER BY count DESC LIMIT ?"
        params.append(limit)

        rows = db.execute(query, params).fetchall()

        routes = []
        for r in rows:
            pace = r['avg_pace']
            pace_str = f"{int(pace//60)}:{int(pace%60):02d}/km" if pace else '-'
            routes.append({
                'area': r['area'] or '未知区域',
                'count': r['count'],
                'distance_km': round((r['total_distance'] or 0) / 1000, 1),
                'avg_pace': pace_str,
                'latest_activity': (r['latest_activity'] or '')[:10],
            })

        return routes

    def _get_default_city(self, db):
        """Get default city and map center based on data."""
        # Find city with most activities
        row = db.execute("""
            SELECT city, COUNT(*) as cnt
            FROM activity_route_summary
            WHERE city IS NOT NULL
            GROUP BY city ORDER BY cnt DESC LIMIT 1
        """).fetchone()

        default_city = row['city'] if row else None

        # Get center from route summaries
        if default_city:
            center_row = db.execute("""
                SELECT AVG(center_lat) as lat, AVG(center_lng) as lng,
                       MIN(min_lat) as min_lat, MAX(max_lat) as max_lat,
                       MIN(min_lng) as min_lng, MAX(max_lng) as max_lng
                FROM activity_route_summary WHERE city = ?
            """, (default_city,)).fetchone()
        else:
            center_row = db.execute("""
                SELECT AVG(center_lat) as lat, AVG(center_lng) as lng,
                       MIN(min_lat) as min_lat, MAX(max_lat) as max_lat,
                       MIN(min_lng) as min_lng, MAX(max_lng) as max_lng
                FROM activity_route_summary
            """).fetchone()

        if center_row and center_row['lat']:
            center = {'lat': center_row['lat'], 'lng': center_row['lng']}
            bounds = {
                'min_lat': center_row['min_lat'],
                'max_lat': center_row['max_lat'],
                'min_lng': center_row['min_lng'],
                'max_lng': center_row['max_lng'],
            }
        else:
            # Default to Shanghai if no data
            center = {'lat': 31.23, 'lng': 121.47}
            bounds = None

        return default_city, center, bounds
