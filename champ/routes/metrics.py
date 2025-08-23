# champ/routes/metrics.py
from flask import Blueprint, request
from champ.db.fetch import run_query

metrics_bp = Blueprint("metrics", __name__)

@metrics_bp.route("/overview_series", methods=["GET"])
def overview_series():
    user_id = request.args.get("user_id")
    if not user_id:
        return {"error": "Missing user_id"}, 400

    sql_last10 = """
    WITH last10 AS (
      SELECT id, start_time, end_time, posture_score, gait_symmetry, balance_score, step_count
      FROM sessions
      WHERE user_id = %s
      ORDER BY start_time DESC
      LIMIT 10
    )
    SELECT
      id,
      start_time,
      TIMESTAMPDIFF(SECOND, start_time, end_time) AS dur_sec,
      posture_score,
      gait_symmetry,
      balance_score,
      step_count
    FROM last10
    ORDER BY start_time ASC;
    """
    rows = run_query(sql_last10, [user_id])

    sql_counts = """
    WITH last10 AS (
      SELECT id
      FROM sessions
      WHERE user_id = %s
      ORDER BY start_time DESC
      LIMIT 10
    )
    SELECT
      (SELECT COUNT(*) FROM alerts WHERE session_id IN (SELECT id FROM last10)) AS alerts_count,
      (SELECT COUNT(*) FROM recommendations WHERE session_id IN (SELECT id FROM last10)) AS recs_count;
    """
    counts = run_query(sql_counts, [user_id])
    counts = counts[0] if counts else {"alerts_count": 0, "recs_count": 0}

    series = {
        "labels": [str(r["start_time"]) for r in rows],
        "posture": [r["posture_score"] for r in rows],
        "gait": [r["gait_symmetry"] for r in rows],
        "balance": [r["balance_score"] for r in rows],
        "steps": [r["step_count"] for r in rows],
        "duration_sec": [r["dur_sec"] for r in rows],
        "alerts_count": counts.get("alerts_count", 0),
        "recs_count": counts.get("recs_count", 0),
    }

    durs = [d for d in series["duration_sec"] if d is not None]
    med = None
    if durs:
        s = sorted(durs)
        n = len(s)
        med = (s[(n-1)//2] + s[n//2]) / 2 if n % 2 == 0 else s[n//2]
    series["duration_median_sec"] = med

    return {"series": series}

@metrics_bp.route("/overview_aggregates", methods=["GET"])
def overview_aggregates():
    user_id = request.args.get("user_id")
    if not user_id:
        return {"error": "Missing user_id"}, 400

    sql = """
    WITH last10 AS (
      SELECT id, start_time, end_time, posture_score, gait_symmetry, balance_score, step_count
      FROM sessions
      WHERE user_id = %s
      ORDER BY start_time DESC
      LIMIT 10
    ),
    dur AS (
      SELECT
        id,
        TIMESTAMPDIFF(SECOND, start_time, end_time) AS dur_sec,
        ROW_NUMBER() OVER (ORDER BY TIMESTAMPDIFF(SECOND, start_time, end_time)) AS rn,
        COUNT(*) OVER () AS cnt
      FROM last10
    ),
    median_dur AS (
      SELECT AVG(dur_sec) AS med_sec
      FROM dur
      WHERE rn IN (FLOOR((cnt+1)/2), CEIL((cnt+1)/2))
    ),
    long_hist AS (
      SELECT
        COUNT(*) AS total_sessions,
        AVG(posture_score) AS avg_posture_all,
        AVG(gait_symmetry) AS avg_gait_all,
        AVG(balance_score) AS avg_balance_all,
        AVG(step_count) AS avg_steps_all
      FROM sessions
      WHERE user_id = %s
    ),
    last10_stats AS (
      SELECT
        AVG(posture_score) AS avg_posture_10,
        AVG(gait_symmetry) AS avg_gait_10,
        AVG(balance_score) AS avg_balance_10,
        AVG(step_count) AS avg_steps_10
      FROM last10
    ),
    short_sess AS (
      SELECT COUNT(*) AS short_sessions_10
      FROM dur, median_dur
      WHERE dur.dur_sec < median_dur.med_sec
    ),
    alerts_10 AS (
      SELECT COUNT(*) AS recent_alerts
      FROM alerts
      WHERE session_id IN (SELECT id FROM last10)
    ),
    recs_10 AS (
      SELECT COUNT(*) AS recent_recs
      FROM recommendations
      WHERE session_id IN (SELECT id FROM last10)
    )
    SELECT
      lh.total_sessions,
      lh.avg_posture_all, lh.avg_gait_all, lh.avg_balance_all, lh.avg_steps_all,
      l10.avg_posture_10, l10.avg_gait_10, l10.avg_balance_10, l10.avg_steps_10,
      ss.short_sessions_10,
      a10.recent_alerts,
      r10.recent_recs
    FROM long_hist lh
    JOIN last10_stats l10 ON 1=1
    JOIN short_sess ss ON 1=1
    JOIN alerts_10 a10 ON 1=1
    JOIN recs_10 r10 ON 1=1;
    """
    rows = run_query(sql, [user_id, user_id])
    return {"aggregates": rows[0] if rows else {}}
