from backend.llm_client import LLMClient
import math

AGENT_PROMPTS = {
    'analyst': """你是运动数据分析师，拥有运动科学背景，擅长从训练数据中提取统计规律和异常检测。

基于提供的训练数据，分析以下内容:
1. 训练数据统计特征（跑量、强度分布、频率）
2. 异常检测（训练中断、强度突然变化）
3. 数据中的模式与趋势
4. 与标准训练模型的对比

请用数据和具体数字支撑你的分析。注意：VDOT 和成绩预测已由系统基于最佳成绩精确计算并给出，请直接引用这些数值，不要重新估算。

【硬规则 - 必须严格遵守】
1. 强度分布分析必须引用系统给出的 E/M/T/I/R 配速区间，不能自行推断区间边界。
2. 配速落在 E 区间（轻松跑）范围内的训练，必须归类为"轻松跑"，不能错误标注为马拉松配速或乳酸阈值。
3. 同一天多条连续跑步记录（间隔很短、距离较短）通常是热身/主训练/冷身的分段记录，不是多次独立训练。遇到此类模式应标注为"分段训练"，而非"同日多次训练"。
4. 禁止仅凭"平均训练配速快于预测马拉松配速"推断糖原消耗过多或有氧基础不足。必须结合心率数据、系统区间和分段事实进行综合判断。""",

    'coach': """你是实战派跑步教练，注重周期化训练、配速策略、伤病预防。

基于数据分析师的分析结果和系统提供的VDOT数据，给出:
1. 训练计划评估与调整建议（基于系统给出的各配速区间）
2. 配速策略优化
3. 伤病风险评估与预防建议
4. 下一阶段训练重点

建议需具体、可操作，结合用户实际水平。配速区间请使用系统给出的数据。

【硬规则 - 必须严格遵守】
1. 强度分布必须基于系统 E/M/T/I/R 区间判断，不能自行推断。
2. 落在 E 区间的配速就是轻松跑，不能错误归类为 M 或 T 区间。
3. 同一天多条连续记录（间隔短、距离短）是分段训练（热身/主训练/冷身），不是多次独立训练，不得违反恢复原则进行批评。
4. 禁止仅凭配速推断糖原消耗或有氧缺失，必须结合心率和区间数据。""",

    'strength': """你是力量与体能训练专家，专注于力量训练对跑步表现的转化效果。

基于数据分析师和跑步教练的讨论，分析:
1. 当前力量训练量与跑步训练的匹配度
2. 力量训练对跑步经济的改善效果
3. 力量训练的周期化建议
4. 需要加强的肌群与动作建议""",

    'summarizer': """你是主教练，负责整合各方专家意见，形成最终的训练报告。

报告需包含以下四部分:
1. **训练数据统计分析**: 基于数据分析师的观点总结
2. **跑步能力趋势**: 能力变化趋势与评估（使用系统给出的VDOT和成绩预测数据，直接引用，不要重新计算）
3. **训练建议**: 综合教练与专家的具体建议
4. **成绩预测**: 引用系统给出的VDOT值和各距离预测成绩表格

报告使用 Markdown 格式，结构清晰，便于阅读。

【硬规则 - 必须严格遵守】
1. 强度分布必须基于系统 E/M/T/I/R 区间判断。
2. 同一天多条连续记录是分段训练，不是多次独立训练。
3. 禁止仅凭配速推断糖原消耗或有氧缺失。"""
}

# Daniels/Gilbert VDOT formula.
# VDOT = oxygen demand at race velocity / sustainable fraction of VO2max.

TRAINING_PACES = {
    '轻松跑 (E)': (0.72, 0.82),
    '马拉松配速 (M)': (0.82, 0.90),
    '乳酸阈值 (T)': (0.90, 0.96),
    '间歇跑 (I)': (0.96, 1.02),
    '重复跑 (R)': (1.02, 1.10),
}

def _calc_vo2(v_m_per_min):
    """Oxygen cost (ml/kg/min) at velocity v (m/min)."""
    return -4.60 + 0.182258 * v_m_per_min + 0.000104 * v_m_per_min ** 2

def _calc_vo2_fraction(time_minutes):
    """Fraction of VO2max sustainable for a race lasting time_minutes."""
    return (
        0.8
        + 0.1894393 * math.exp(-0.012778 * time_minutes)
        + 0.2989558 * math.exp(-0.1932605 * time_minutes)
    )

def _calc_v_from_vo2(vo2):
    """Solve for velocity (m/min) given oxygen cost."""
    a, b, c = 0.000104, 0.182258, -4.60 - vo2
    disc = b * b - 4 * a * c
    if disc < 0:
        return 0
    return (-b + math.sqrt(disc)) / (2 * a)

def _calc_vdot_raw(distance_m, time_seconds):
    """Unrounded VDOT from a race performance."""
    if time_seconds <= 0 or distance_m <= 0:
        return 0
    time_minutes = time_seconds / 60.0
    v = distance_m / time_minutes
    fraction = _calc_vo2_fraction(time_minutes)
    if fraction <= 0:
        return 0
    return _calc_vo2(v) / fraction

def calc_vdot(distance_m, time_seconds):
    """Calculate VDOT from a race performance using the Daniels/Gilbert formula."""
    return round(_calc_vdot_raw(distance_m, time_seconds), 1)

def predict_time(vdot, distance_m):
    """Predict race time (minutes) by solving the Daniels/Gilbert VDOT equation."""
    if vdot <= 0 or distance_m <= 0:
        return None
    low, high = 1.0, 600.0
    for _ in range(80):
        mid = (low + high) / 2
        candidate = _calc_vdot_raw(distance_m, mid * 60)
        if candidate > vdot:
            low = mid
        else:
            high = mid
    return (low + high) / 2

def predict_time_str(vdot, distance_m):
    """Predicted time as h:mm:ss string."""
    t = predict_time(vdot, distance_m)
    if t is None:
        return 'N/A'
    total_s = int(round(t * 60))
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def _sec_to_pace(sec_per_km):
    """Convert seconds per km to m:ss pace string."""
    if not sec_per_km:
        return '-'
    m = int(sec_per_km // 60)
    s = int(sec_per_km % 60)
    return f"{m}:{s:02d}"


RACE_DISTANCES = {
    '5K': 5000,
    '10K': 10000,
    '半马': 21097.5,
    '全马': 42195,
}


class ReportGenerator:
    def __init__(self, base_url, api_key, model, rounds=4):
        self.llm = LLMClient(base_url, api_key, model)
        self.rounds = min(max(rounds, 3), 5)

    def generate(self, training_data):
        conversation = []
        has_strength = training_data.get('has_strength', False)

        data_context = self._build_data_context(training_data)

        analyst_msg = self._agent_turn('analyst', data_context, conversation)
        conversation.append({'agent': 'analyst', 'content': analyst_msg})

        for r in range(2, self.rounds + 1):
            analyst_reply = self.llm.chat(
                self._build_cross_talk_prompt('analyst', conversation)
            )
            conversation.append({'agent': 'analyst', 'content': analyst_reply})

            coach_reply = self.llm.chat(
                self._build_cross_talk_prompt('coach', conversation)
            )
            conversation.append({'agent': 'coach', 'content': coach_reply})

            if has_strength:
                strength_reply = self.llm.chat(
                    self._build_cross_talk_prompt('strength', conversation)
                )
                conversation.append({'agent': 'strength', 'content': strength_reply})

        final_report = self.llm.chat(
            self._build_summarizer_prompt(conversation, data_context),
            max_tokens=8192
        )

        return final_report

    def generate_stream(self, training_data):
        has_strength = training_data.get('has_strength', False)
        conversation = []
        data_context = self._build_data_context(training_data)

        yield {'status': 'running', 'round': 1, 'agent': 'analyst', 'phase': '数据分析师分析中...'}
        analyst_msg = self._agent_turn('analyst', data_context, conversation)
        conversation.append({'agent': 'analyst', 'content': analyst_msg})

        for r in range(2, self.rounds + 1):
            yield {'status': 'running', 'round': r, 'agent': 'analyst', 'phase': f'第{r}轮讨论 - 数据分析师...'}
            conversation.append({'agent': 'analyst', 'content': self.llm.chat(
                self._build_cross_talk_prompt('analyst', conversation)
            )})

            yield {'status': 'running', 'round': r, 'agent': 'coach', 'phase': f'第{r}轮讨论 - 跑步教练...'}
            conversation.append({'agent': 'coach', 'content': self.llm.chat(
                self._build_cross_talk_prompt('coach', conversation)
            )})

            if has_strength:
                yield {'status': 'running', 'round': r, 'agent': 'strength', 'phase': f'第{r}轮讨论 - 力量专家...'}
                conversation.append({'agent': 'strength', 'content': self.llm.chat(
                    self._build_cross_talk_prompt('strength', conversation)
                )})

        yield {'status': 'running', 'agent': 'summarizer', 'phase': '主教练整合报告中...'}
        final_report = self.llm.chat(
            self._build_summarizer_prompt(conversation, data_context),
            max_tokens=8192
        )

        yield {'status': 'done', 'report': final_report}

    def _build_data_context(self, data):
        lines = [f"""训练数据摘要:
- 时间范围: {data.get('date_range', '全部')}
- 总跑步次数: {data.get('total_runs', 0)}
- 总跑量: {data.get('total_distance', 0)/1000:.1f} km
- 总训练时间: {data.get('total_duration', 0)/3600:.1f} 小时
- 平均配速: {data.get('avg_pace', 0):.0f} 秒/公里
- 平均心率: {data.get('avg_hr', 0):.0f} bpm
- 海拔总爬升: {data.get('total_elevation', 0):.0f} m
- 包含力量训练数据: {'是' if data.get('has_strength') else '否'}"""]

        profile = data.get('profile', {})
        if any(profile.values()):
            lines.append('\n跑者信息:')
            if profile.get('age'): lines.append(f'- 年龄: {profile["age"]}')
            if profile.get('gender'): lines.append(f'- 性别: {"男" if profile["gender"]=="male" else "女"}')
            if profile.get('height'): lines.append(f'- 身高: {profile["height"]} cm')
            if profile.get('weight'): lines.append(f'- 体重: {profile["weight"]} kg')
            if profile.get('resting_hr'): lines.append(f'- 静息心率: {profile["resting_hr"]} bpm')
            if profile.get('max_hr'): lines.append(f'- 最大心率: {profile["max_hr"]} bpm')
            if profile.get('race_goal'):
                goal_map = {'5k': '5K', '10k': '10K', 'half_marathon': '半马', 'marathon': '全马'}
                lines.append(f'- 跑步目标: {goal_map.get(profile["race_goal"], profile["race_goal"])}')

        performances = data.get('performances', {})
        vdot = performances.get('vdot', 0)
        if vdot > 0:
            lines.append(f'\n## 跑力 (VDOT) 分析（系统精确计算，请直接引用）')
            lines.append(f'- 当前 VDOT: **{vdot}**')
            lines.append(f'- 计算依据: {performances.get("source", "最佳5K成绩")}')
            lines.append('')
            lines.append('成绩预测（基于 VDOT）:')
            lines.append('| 距离 | 预测成绩 | 配速 |')
            lines.append('|------|---------|------|')
            for dist_name, dist_m in RACE_DISTANCES.items():
                pred_time = predict_time_str(vdot, dist_m)
                pace_sec = predict_time(vdot, dist_m)
                if pace_sec:
                    pace_str = _sec_to_pace(pace_sec * 60 / dist_m * 1000)
                else:
                    pace_str = '-'
                lines.append(f'| {dist_name} | {pred_time} | {pace_str}/km |')

            lines.append('')
            lines.append('训练配速区间:')
            lines.append('| 训练类型 | 配速范围 |')
            lines.append('|---------|---------|')
            for pace_name, (lo, hi) in TRAINING_PACES.items():
                v = _calc_v_from_vo2(vdot)
                if v > 0:
                    base_pace = 1000 / v * 60
                    lo_pace = base_pace / hi
                    hi_pace = base_pace / lo
                    lines.append(f'| {pace_name} | {_sec_to_pace(lo_pace)} ~ {_sec_to_pace(hi_pace)} /km |')

            if performances.get('best_5k'):
                lines.append(f'\n最近最佳 5K: {performances["best_5k"]}')

        # HR zones from profile
        profile = data.get('profile', {})
        rhr_str = profile.get('resting_hr', '')
        mhr_str = profile.get('max_hr', '')
        if rhr_str and mhr_str:
            try:
                rhr = int(rhr_str)
                mhr = int(mhr_str)
                reserve = mhr - rhr
                lines.append('\n## 心率区间（储备心率法，请直接引用）')
                lines.append(f'- 静息心率: {rhr} bpm / 最大心率: {mhr} bpm')
                lines.append('| 区间 | 心率范围 | 用途 |')
                lines.append('|------|---------|------|')
                lines.append(f'| 1 (恢复/热身) | {rhr} ~ {round(rhr+reserve*0.60)} | 恢复跑、热身 |')
                lines.append(f'| 2 (燃脂/轻松跑E) | {round(rhr+reserve*0.60)} ~ {round(rhr+reserve*0.70)} | 轻松跑、长距离 |')
                lines.append(f'| 3 (有氧/马拉松M) | {round(rhr+reserve*0.70)} ~ {round(rhr+reserve*0.80)} | 马拉松配速、节奏跑 |')
                lines.append(f'| 4 (阈值T) | {round(rhr+reserve*0.80)} ~ {round(rhr+reserve*0.90)} | 乳酸阈值跑 |')
                lines.append(f'| 5 (最大摄氧I) | {round(rhr+reserve*0.90)} ~ {mhr} | 间歇跑、VO2max训练 |')
            except ValueError:
                pass

        if data.get('recent'):
            lines.append(f'\n近期训练概要: {data["recent"]}')

        if data.get('split_context'):
            lines.append(data['split_context'])

        # Add training day merge summary
        activities = data.get('activities', [])
        if activities:
            merged_summary = self._build_training_day_summary(activities)
            if merged_summary:
                lines.append(merged_summary)

        activities = data.get('activities', [])
        if activities:
            has_dynamics = any(a.get('avg_cadence') or a.get('avg_ground_contact_time') for a in activities)
            has_weather = any(a.get('temperature') is not None or a.get('weather_condition') for a in activities)
            if has_dynamics or has_weather:
                lines.append(f'\n## 近期训练记录明细 (共{len(activities)}条)')
                if has_weather:
                    lines.append('| 日期 | 名称 | 距离 | 配速 | 心率 | 步频 | 触地 | 振幅 | 温度 | 天气 |')
                    lines.append('|------|------|------|------|------|------|------|------|------|------|')
                    type_cn = {'running': '跑步', 'strength_training': '力量', 'cycling': '骑行', 'lap_swimming': '游泳'}
                    for a in activities:
                        date = (a.get('start_time', ''))[:10]
                        d = f'{a["distance"]/1000:.2f}km' if a.get('distance') else '-'
                        pace = f'{a["avg_pace"]:.0f}s/km' if a.get('avg_pace') else '-'
                        hr = f'{round(a["avg_heart_rate"])}' if a.get('avg_heart_rate') else '-'
                        cad = f'{round(a["avg_cadence"])}' if a.get('avg_cadence') else '-'
                        gct = f'{round(a["avg_ground_contact_time"])}ms' if a.get('avg_ground_contact_time') else '-'
                        vo = f'{a["avg_vertical_oscillation"]:.1f}cm' if a.get('avg_vertical_oscillation') else '-'
                        temp = f'{a["temperature"]:.1f}°C' if a.get('temperature') is not None else '-'
                        cond = a.get('weather_condition', '-') or '-'
                        lines.append(f'| {date} | {a.get("name","")} | {d} | {pace} | {hr} | {cad} | {gct} | {vo} | {temp} | {cond} |')
                else:
                    lines.append('| 日期 | 名称 | 距离 | 配速 | 心率 | 步频 | 触地 | 振幅 |')
                    lines.append('|------|------|------|------|------|------|------|------|')
                    type_cn = {'running': '跑步', 'strength_training': '力量', 'cycling': '骑行', 'lap_swimming': '游泳'}
                    for a in activities:
                        date = (a.get('start_time', ''))[:10]
                        d = f'{a["distance"]/1000:.2f}km' if a.get('distance') else '-'
                        pace = f'{a["avg_pace"]:.0f}s/km' if a.get('avg_pace') else '-'
                        hr = f'{round(a["avg_heart_rate"])}' if a.get('avg_heart_rate') else '-'
                        cad = f'{round(a["avg_cadence"])}' if a.get('avg_cadence') else '-'
                        gct = f'{round(a["avg_ground_contact_time"])}ms' if a.get('avg_ground_contact_time') else '-'
                        vo = f'{a["avg_vertical_oscillation"]:.1f}cm' if a.get('avg_vertical_oscillation') else '-'
                        lines.append(f'| {date} | {a.get("name","")} | {d} | {pace} | {hr} | {cad} | {gct} | {vo} |')
            else:
                lines.append(f'\n## 近期训练记录明细 (共{len(activities)}条)')
                lines.append('| 日期 | 类型 | 名称 | 距离 | 时长 | 配速 | 心率 |')
                lines.append('|------|------|------|------|------|------|------|')
                type_cn = {'running': '跑步', 'strength_training': '力量', 'cycling': '骑行', 'lap_swimming': '游泳'}
                for a in activities:
                    t = type_cn.get(a.get('type', ''), a.get('type', '其他'))
                    d = f'{a["distance"]/1000:.2f}km' if a.get('distance') else '-'
                    dur = f'{a["duration"]/60:.0f}min' if a.get('duration') else '-'
                    pace = f'{a["avg_pace"]:.0f}s/km' if a.get('avg_pace') else '-'
                    hr = f'{round(a["avg_heart_rate"])}' if a.get('avg_heart_rate') else '-'
                    date = (a.get('start_time', ''))[:10]
                    lines.append(f'| {date} | {t} | {a.get("name", "")} | {d} | {dur} | {pace} | {hr} |')

        # Health data
        health = data.get('health_data', [])
        if health:
            lines.append(f'\n## 近期健康数据')
            lines.append('| 日期 | HRV | 睡眠 | 时长 | 静息HR | 压力 | 身体电量 |')
            lines.append('|------|-----|------|------|--------|------|---------|')
            for h in health[-14:]:
                hrv = f'{round(h["hrv_avg"])}' if h.get('hrv_avg') else '-'
                slp = f'{h["sleep_score"]}' if h.get('sleep_score') else '-'
                dur = f'{h["sleep_duration"]}h' if h.get('sleep_duration') else '-'
                rhr = f'{round(h["resting_hr"])}' if h.get('resting_hr') else '-'
                stress = f'{round(h["avg_stress"])}' if h.get('avg_stress') else '-'
                bb = f'{h["body_battery_max"]}/{h["body_battery_min"]}' if h.get('body_battery_max') else '-'
                lines.append(f'| {h["date"]} | {hrv} | {slp} | {dur} | {rhr} | {stress} | {bb} |')

        return '\n'.join(lines)

    def _agent_turn(self, agent, data_context, conversation):
        agent_prompt = AGENT_PROMPTS[agent]
        messages = [
            {'role': 'system', 'content': agent_prompt},
            {'role': 'user', 'content': f'请开始你的分析。\n\n{data_context}'}
        ]
        return self.llm.chat(messages)

    def _build_cross_talk_prompt(self, agent, conversation):
        agent_prompt = AGENT_PROMPTS[agent]
        context = "以下是到目前为止的讨论记录:\n\n"
        for entry in conversation[-6:]:
            context += f"【{entry['agent']}】: {entry['content'][:2000]}\n\n"

        context += f"\n请【{agent}】基于以上讨论发表你的看法。可以赞同、补充或礼貌地提出不同意见。"
        return [
            {'role': 'system', 'content': agent_prompt},
            {'role': 'user', 'content': context}
        ]

    def _build_summarizer_prompt(self, conversation, data_context):
        context = "以下是完整讨论记录:\n\n"
        for entry in conversation:
            context += f"【{entry['agent']}】: {entry['content'][:3000]}\n\n"

        context += f"\n原始数据:\n{data_context}"
        context += "\n请整合以上所有意见，生成最终训练报告。"

        return [
            {'role': 'system', 'content': AGENT_PROMPTS['summarizer']},
            {'role': 'user', 'content': context}
        ]

    def _build_training_day_summary(self, activities):
        """Detect same-day consecutive runs and build a merge summary.
        
        If multiple runs on the same day have short gaps (< 30 min) and
        shorter distances, they are likely warmup/main/cooldown segments.
        """
        from datetime import datetime, timedelta
        
        # Group activities by date
        day_groups = {}
        for a in activities:
            date = (a.get('start_time', ''))[:10]
            if not date:
                continue
            if date not in day_groups:
                day_groups[date] = []
            day_groups[date].append(a)
        
        # Find days with multiple activities
        merged_days = []
        for date, acts in sorted(day_groups.items(), reverse=True):
            if len(acts) < 2:
                continue
            
            # Sort by start time
            acts_sorted = sorted(acts, key=lambda x: x.get('start_time', ''))
            
            # Check if they look like segments (short gaps, shorter initial/final runs)
            is_segment = True
            for i in range(1, len(acts_sorted)):
                try:
                    prev_end = datetime.strptime(acts_sorted[i-1].get('start_time', '')[:19], '%Y-%m-%d %H:%M:%S')
                    curr_start = datetime.strptime(acts_sorted[i].get('start_time', '')[:19], '%Y-%m-%d %H:%M:%S')
                    gap = (curr_start - prev_end).total_seconds() / 60
                    if gap > 30:  # More than 30 min gap = separate sessions
                        is_segment = False
                        break
                except (ValueError, TypeError):
                    is_segment = False
                    break
            
            if is_segment and len(acts_sorted) >= 2:
                total_dist = sum(a.get('distance', 0) or 0 for a in acts_sorted) / 1000
                total_dur = sum(a.get('duration', 0) or 0 for a in acts_sorted) / 60
                merged_days.append({
                    'date': date,
                    'count': len(acts_sorted),
                    'total_distance': total_dist,
                    'total_duration': total_dur,
                    'segments': [f"{(a.get('distance', 0) or 0)/1000:.1f}km" for a in acts_sorted]
                })
        
        if not merged_days:
            return ''
        
        lines = ['\n## 分段训练说明（同日多次记录）']
        lines.append('以下日期存在同日多次跑步记录，间隔较短，应为热身/主训练/冷身的分段记录：')
        lines.append('| 日期 | 分段数 | 总距离 | 总时长 | 各段距离 |')
        lines.append('|------|--------|--------|--------|----------|')
        for d in merged_days[:5]:  # Show max 5 days
            segments_str = ' → '.join(d['segments'])
            lines.append(f"| {d['date']} | {d['count']}段 | {d['total_distance']:.1f}km | {d['total_duration']:.0f}min | {segments_str} |")
        
        return '\n'.join(lines)
