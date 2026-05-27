"""Calibration drift detection using Welford's online algorithm."""

from .database import get_connection


def _welford_update(count, mean, m2, new_value):
    """Pure-function Welford update. Returns (count+1, new_mean, new_m2)."""
    count += 1
    delta = new_value - mean
    mean += delta / count
    delta2 = new_value - mean
    m2 += delta * delta2
    return count, mean, m2


class CalibrationTracker:
    """Track running per-dimension statistics via Welford's algorithm."""

    def update(self, report_type, dimension_id, score):
        """Read current row from DB, apply Welford, write back."""
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT count, mean, m2, min_value, max_value FROM calibration_metrics "
                "WHERE report_type = ? AND dimension_id = ?",
                (report_type, dimension_id),
            ).fetchone()
            if row:
                count, mean, m2 = row["count"], row["mean"], row["m2"]
                min_val = min(row["min_value"] or score, score)
                max_val = max(row["max_value"] or score, score)
            else:
                count, mean, m2 = 0, 0.0, 0.0
                min_val, max_val = score, score

            count, mean, m2 = _welford_update(count, mean, m2, score)

            conn.execute(
                "INSERT OR REPLACE INTO calibration_metrics "
                "(report_type, dimension_id, count, mean, m2, min_value, max_value, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (report_type, dimension_id, count, mean, m2, min_val, max_val),
            )
            conn.commit()
        finally:
            conn.close()

    def get_stats(self, report_type):
        """Return per-dimension stats for a report_type."""
        from math import sqrt
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT dimension_id, count, mean, m2, min_value, max_value "
                "FROM calibration_metrics WHERE report_type = ? ORDER BY dimension_id",
                (report_type,),
            ).fetchall()
            result = []
            for r in rows:
                stddev = sqrt(r["m2"] / r["count"]) if r["count"] >= 2 else None
                result.append({
                    "dimension_id": r["dimension_id"],
                    "count": r["count"],
                    "mean": r["mean"],
                    "stddev": stddev,
                    "min": r["min_value"],
                    "max": r["max_value"],
                })
            return result
        finally:
            conn.close()


def get_calibration_stats(report_type):
    """Convenience function."""
    return CalibrationTracker().get_stats(report_type)
