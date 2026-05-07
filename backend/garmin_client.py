import os
from garminconnect import Garmin
from garminconnect.exceptions import (
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)


_CN_PATCHES = {
    'DI_TOKEN_URL': 'https://diauth.garmin.cn/di-oauth2-service/oauth/token',
    'IOS_SERVICE_URL': 'https://connect.garmin.cn/modern/',
}
_ORIGINALS = {}
_saved_methods = {}


def _get_gc_client():
    import garminconnect.client as c
    return c


def _patch_for_cn():
    gc = _get_gc_client()
    for attr, cn_url in _CN_PATCHES.items():
        if attr not in _ORIGINALS:
            _ORIGINALS[attr] = getattr(gc, attr)
        setattr(gc, attr, cn_url)

    if not _saved_methods:
        _saved_methods['establish_session'] = gc.Client._establish_session
        _saved_methods['mobile_login_cffi'] = gc.Client._mobile_login_cffi
        _saved_methods['mobile_login_requests'] = gc.Client._mobile_login_requests
        _saved_methods['widget_web_login'] = gc.Client._widget_web_login

        def _cn_establish(self, ticket, sess=None, service_url=None):
            try:
                _saved_methods['establish_session'](self, ticket, sess=sess, service_url=service_url)
                return
            except gc.GarminConnectAuthenticationError:
                if self.domain != "garmin.cn":
                    raise

            if sess is not None:
                self.cs = sess

            self.cs.get(
                f"{self._connect}/modern/",
                params={"ticket": ticket},
                allow_redirects=True,
                timeout=30,
            )

            for c in self.cs.cookies.jar:
                if c.name == "JWT_WEB":
                    self.jwt_web = c.value
                    break

            if not self.jwt_web:
                raise gc.GarminConnectAuthenticationError(
                    "JWT_WEB cookie not set after CN ticket consumption"
                )

        def _skip_strategy(self, email, password):
            raise gc.GarminConnectTooManyRequestsError("Skipped for CN")

        gc.Client._establish_session = _cn_establish
        gc.Client._mobile_login_cffi = _skip_strategy
        gc.Client._mobile_login_requests = _skip_strategy
        gc.Client._widget_web_login = _skip_strategy


def _restore_patches():
    global _ORIGINALS, _saved_methods
    gc = _get_gc_client()
    for attr, orig in _ORIGINALS.items():
        setattr(gc, attr, orig)
    if _saved_methods:
        gc.Client._establish_session = _saved_methods['establish_session']
        gc.Client._mobile_login_cffi = _saved_methods['mobile_login_cffi']
        gc.Client._mobile_login_requests = _saved_methods['mobile_login_requests']
        gc.Client._widget_web_login = _saved_methods['widget_web_login']
    _saved_methods = {}


class GarminClient:
    def __init__(self, tokenstore=None):
        self.client = None
        self.email = None
        self.session_token = None
        if tokenstore:
            self._tokenstore = os.path.abspath(tokenstore)
        else:
            self._tokenstore = os.environ.get('GARMIN_TOKENSTORE')
            if not self._tokenstore:
                from backend.database import _get_db_path
                db_path = _get_db_path()
                self._tokenstore = os.path.join(os.path.dirname(db_path), 'garmin_tokens')
            self._tokenstore = os.path.abspath(self._tokenstore)

    def login(self, email, password):
        for attempt, is_cn in enumerate([True, False]):
            try:
                label = '国际区' if not is_cn else '中国区'
                if is_cn:
                    _patch_for_cn()
                self.client = Garmin(email, password, is_cn=is_cn)
                self.client.login(tokenstore=self._tokenstore)
                self.email = email
                self._last_is_cn = is_cn
                return {'success': True, 'region': label}
            except GarminConnectTooManyRequestsError:
                if is_cn:
                    _restore_patches()
                if attempt == 1:
                    return {'success': False, 'error': '请求过于频繁，请稍后重试'}
            except GarminConnectAuthenticationError as e:
                error_msg = str(e)
                if is_cn:
                    _restore_patches()
                if '验证码' in error_msg or 'captcha' in error_msg.lower():
                    return {'success': False, 'error': '需要验证码', 'need_captcha': True}
                if attempt == 1:
                    return {
                        'success': False,
                        'error': f'佳明认证失败: {error_msg}',
                        'detail': '请确认账号密码正确。若持续失败，可尝试登录 https://connect.garmin.cn 确认账号状态',
                    }
            except Exception as e:
                if is_cn:
                    _restore_patches()
                if attempt == 1:
                    return {'success': False, 'error': f'登录异常: {str(e)}'}

        return {'success': False, 'error': '登录失败，请检查网络连接'}

    def fetch_activities(self, start=0, limit=100):
        if not self.client:
            raise RuntimeError("未登录")
        raw = self.client.get_activities(start, limit)
        return [self._parse_activity(a) for a in raw]

    def fetch_activity_detail(self, activity_id):
        if not self.client:
            raise RuntimeError("未登录")
        return self.client.get_activity(activity_id)

    def fetch_activity_details(self, activity_id):
        """Fetch detailed activity data with running dynamics.
        Tries get_activity(summary) first, then get_activity_details(metrics)."""
        if not self.client:
            raise RuntimeError("未登录")
        detail = {}
        # Get summary data (contains cadence, ground contact time, etc.)
        try:
            summary = self.client.get_activity(activity_id)
            if summary:
                detail['summary'] = summary
        except Exception:
            pass
        # Get raw metrics for completeness
        try:
            metrics = self.client.get_activity_details(activity_id)
            if metrics:
                detail['metrics'] = metrics
        except Exception:
            pass
        if not detail:
            return None
        return self._parse_detail(detail)

    def _parse_detail(self, detail):
        result = {}
        result['detail_json'] = str(detail)

        summary = detail.get('summary', {})
        if isinstance(summary, dict):
            sw = summary.get('summaryDTO', summary)

            # China Garmin API field names (different from international)
            if 'averageRunCadence' in sw:
                result['avg_cadence'] = sw['averageRunCadence']
            elif 'avgRunningCadenceInStepsPerMinute' in sw:
                result['avg_cadence'] = sw['avgRunningCadenceInStepsPerMinute']
            if 'maxRunCadence' in sw:
                result['max_cadence'] = sw['maxRunCadence']
            elif 'maxRunningCadenceInStepsPerMinute' in sw:
                result['max_cadence'] = sw['maxRunningCadenceInStepsPerMinute']
            if 'groundContactTime' in sw:
                result['avg_ground_contact_time'] = sw['groundContactTime']
            elif 'avgGroundContactTimeInMilliSeconds' in sw:
                result['avg_ground_contact_time'] = sw['avgGroundContactTimeInMilliSeconds']
            if 'verticalOscillation' in sw:
                result['avg_vertical_oscillation'] = sw['verticalOscillation']
            elif 'avgVerticalOscillationInMilliMeters' in sw:
                result['avg_vertical_oscillation'] = sw['avgVerticalOscillationInMilliMeters']
            if 'strideLength' in sw:
                result['avg_stride_length'] = sw['strideLength']
            elif 'avgStrideLengthInCentimeters' in sw:
                result['avg_stride_length'] = sw['avgStrideLengthInCentimeters']
            if 'trainingEffect' in sw:
                result['training_effect'] = sw['trainingEffect']
            elif 'aerobicTrainingEffect' in sw:
                result['training_effect'] = sw['aerobicTrainingEffect']
            if 'vO2MaxValue' in sw:
                result['vo2max'] = sw['vO2MaxValue']
            lt = sw.get('lactateThresholdBpm')
            if lt is not None:
                result['lactate_threshold'] = lt

            # Try top-level keys too
            for src_key, dst_key in [
                ('averageRunCadence', 'avg_cadence'),
                ('maxRunCadence', 'max_cadence'),
                ('groundContactTime', 'avg_ground_contact_time'),
                ('verticalOscillation', 'avg_vertical_oscillation'),
                ('strideLength', 'avg_stride_length'),
                ('trainingEffect', 'training_effect'),
                ('avgRunningCadenceInStepsPerMinute', 'avg_cadence'),
                ('maxRunningCadenceInStepsPerMinute', 'max_cadence'),
                ('avgGroundContactTimeInMilliSeconds', 'avg_ground_contact_time'),
                ('avgVerticalOscillationInMilliMeters', 'avg_vertical_oscillation'),
                ('avgStrideLengthInCentimeters', 'avg_stride_length'),
                ('aerobicTrainingEffect', 'training_effect'),
                ('vO2MaxValue', 'vo2max'),
            ]:
                if dst_key not in result and src_key in summary:
                    result[dst_key] = summary[src_key]

        return result

    def _parse_activity(self, raw):
        activity_type = raw.get('activityType', {})
        if isinstance(activity_type, dict):
            type_key = activity_type.get('typeKey', 'other')
        else:
            type_key = 'other'

        return {
            'id': raw.get('activityId'),
            'name': raw.get('activityName', ''),
            'type': type_key,
            'start_time': raw.get('startTimeLocal', ''),
            'duration': raw.get('duration', 0),
            'distance': raw.get('distance', 0),
            'avg_heart_rate': raw.get('averageHR'),
            'max_heart_rate': raw.get('maxHR'),
            'avg_pace': self._calc_pace(raw.get('duration'), raw.get('distance')),
            'elevation_gain': raw.get('elevationGain', 0),
            'raw_json': str(raw),
        }

    def _calc_pace(self, duration, distance):
        if not duration or not distance or distance == 0:
            return None
        return duration / (distance / 1000)

    def fetch_health_data(self, date_str):
        """Fetch daily health data for a given date (YYYY-MM-DD)."""
        if not self.client:
            raise RuntimeError("未登录")
        result = {'date': date_str}
        raw_parts = {}

        # HRV
        try:
            hrv = self.client.get_hrv_data(date_str)
            if hrv:
                raw_parts['hrv'] = hrv
                result['hrv_avg'] = hrv.get('hrvSummary', {}).get('lastNightAvg')
                status = hrv.get('hrvSummary', {}).get('status')
                if status:
                    result['hrv_status'] = status
        except Exception:
            pass

        # Sleep
        try:
            sleep = self.client.get_sleep_data(date_str)
            if sleep:
                raw_parts['sleep'] = sleep
                daily = sleep.get('dailySleepDTO', {})
                result['sleep_score'] = daily.get('sleepScores', {}).get('overall', {}).get('value')
                result['sleep_duration'] = daily.get('sleepTimeSeconds')
                if result['sleep_duration']:
                    result['sleep_duration'] = round(result['sleep_duration'] / 3600, 1)
        except Exception:
            pass

        # Body battery
        try:
            bb = self.client.get_body_battery(date_str)
            if bb and isinstance(bb, list):
                vals = [e.get('charged') or e.get('bodyBatteryValue') for e in bb if e.get('charged') is not None or e.get('bodyBatteryValue') is not None]
                vals = [v for v in vals if v is not None]
                if vals:
                    result['body_battery_max'] = max(vals)
                    result['body_battery_min'] = min(vals)
                    raw_parts['body_battery'] = bb
        except Exception:
            pass

        # Stress
        try:
            stress = self.client.get_stress_data(date_str)
            if stress:
                raw_parts['stress'] = stress
                vals = [s.get('value') for s in stress.get('stressValues', []) if s.get('value') is not None]
                if vals:
                    result['avg_stress'] = round(sum(vals) / len(vals), 1)
        except Exception:
            pass

        # Resting HR
        try:
            rhr = self.client.get_rhr_day(date_str)
            if rhr and isinstance(rhr, dict):
                result['resting_hr'] = rhr.get('restingHeartRate')
                raw_parts['rhr'] = rhr
        except Exception:
            pass

        # VO2max from max metrics
        try:
            mm = self.client.get_max_metrics(date_str)
            if mm:
                raw_parts['max_metrics'] = mm
                vo2 = mm.get('generic', {}).get('vo2MaxPrecisionValue') or mm.get('generic', {}).get('vo2MaxValue')
                if vo2:
                    result['vo2max'] = vo2
        except Exception:
            pass

        if raw_parts:
            result['raw_json'] = str(raw_parts)
        return result if len(result) > 1 else None
