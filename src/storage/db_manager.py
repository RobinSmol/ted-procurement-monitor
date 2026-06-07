import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import cast

from src.core.enums import AlertField, NoticeField, ProfileField, StorageConfig
from src.core.interfaces import ReadStorageProtocol, WriteStorageProtocol

logger = logging.getLogger(__name__)

CREATE_TABLE_QUERY = f"""
CREATE TABLE IF NOT EXISTS {StorageConfig.DB_TABLE_NOTICES} (
    {NoticeField.ID}                  TEXT PRIMARY KEY,
    {NoticeField.TITLE}               TEXT NOT NULL,
    {NoticeField.PUB_DATE}            TEXT,
    {NoticeField.COUNTRY}             TEXT,
    {NoticeField.ESTIMATED_VALUE}     REAL,
    {NoticeField.CURRENCY}            TEXT,
    {NoticeField.ESTIMATED_VALUE_EUR} REAL,
    {NoticeField.DESCRIPTION}         TEXT,
    {NoticeField.CPV}                 TEXT,
    {NoticeField.SOURCE_NAME}         TEXT
);
"""

CREATE_EMAIL_ALERTS_QUERY = f"""
CREATE TABLE IF NOT EXISTS {StorageConfig.DB_TABLE_ALERTS} (
    {AlertField.ID}        TEXT PRIMARY KEY,
    {AlertField.EMAIL}     TEXT NOT NULL,
    {AlertField.QUERY}     TEXT,
    {AlertField.CPV_CODES} TEXT,
    {AlertField.THRESHOLD} REAL DEFAULT 0.5,
    {AlertField.SEND_DAYS} TEXT NOT NULL,
    {AlertField.LAST_SENT} TEXT
);
"""
CREATE_PROFILES_QUERY = f"""
CREATE TABLE IF NOT EXISTS {StorageConfig.DB_TABLE_PROFILES} (
    {ProfileField.ID}                  TEXT PRIMARY KEY,
    {ProfileField.NAME}                TEXT NOT NULL,
    {ProfileField.KEYWORDS}            TEXT,
    {ProfileField.NEGATIVE_KEYWORDS}   TEXT,
    {ProfileField.PREFERRED_COUNTRIES} TEXT,
    {ProfileField.CPV_CODES}           TEXT,
    {ProfileField.CREATED_AT}          TEXT
);
"""

CREATE_FETCHED_DATES_QUERY = f"""
CREATE TABLE IF NOT EXISTS {StorageConfig.DB_TABLE_FETCHED_DATES} (
    {StorageConfig.FETCHED_DATES_COLUMN} TEXT PRIMARY KEY
);
"""


class DBManager(WriteStorageProtocol, ReadStorageProtocol):
    """SQLite-backed storage manager for tender notices and fetch tracking.

    Implements both ReadStorageProtocol and WriteStorageProtocol, serving
    as the single interface to the relational database layer. Supports both
    file-based and in-memory databases, the latter being used exclusively
    for testing.

    Attributes:
        db_path: Path to the SQLite database file, or ':memory:' for tests.
        connection: Persistent connection kept alive for in-memory databases.
            None for file-based databases, where connections are created
            per operation.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initializes the database manager and creates tables if needed.

        For file-based databases, ensures the parent directory exists before
        connecting. For in-memory databases, keeps a persistent connection
        alive for the lifetime of the instance.

        Args:
            db_path: Path to the SQLite database file, or ':memory:'
                for an ephemeral in-memory database.
        """
        self.db_path = db_path
        self.connection = None
        if db_path != ":memory:":
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
        self._create_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns an active database connection.

        Returns the persistent connection for in-memory databases,
        or opens a new connection for file-based databases. Callers
        are expected to use this inside a context manager.

        Returns:
            An sqlite3.Connection with row_factory set to sqlite3.Row.
        """
        if self.connection is not None:
            return self.connection
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _create_table(self) -> None:
        """Creates the notices and fetched_dates tables if they do not exist.

        Runs at initialization. Uses IF NOT EXISTS, making this safe
        to call on an already-populated database.
        """
        with self._get_connection() as con:
            con.execute(CREATE_TABLE_QUERY)
            con.execute(CREATE_FETCHED_DATES_QUERY)
            con.execute(CREATE_EMAIL_ALERTS_QUERY)
            con.execute(CREATE_PROFILES_QUERY)

    def save_notices(self, notices: list[dict]) -> None:
        """Persists a batch of normalized notices to the database.

        Uses INSERT OR REPLACE to handle re-runs gracefully — existing
        notices are overwritten rather than raising a constraint error.

        Args:
            notices: List of validated notice dictionaries to persist.
        """
        if not notices:
            return
        query = f"""
        INSERT OR REPLACE INTO {StorageConfig.DB_TABLE_NOTICES} (
            {NoticeField.ID}, {NoticeField.TITLE}, {NoticeField.PUB_DATE}, {NoticeField.COUNTRY},
            {NoticeField.ESTIMATED_VALUE}, {NoticeField.CURRENCY}, {NoticeField.ESTIMATED_VALUE_EUR},
            {NoticeField.DESCRIPTION}, {NoticeField.CPV}, {NoticeField.SOURCE_NAME}
        ) VALUES (
            :{NoticeField.ID}, :{NoticeField.TITLE}, :{NoticeField.PUB_DATE}, :{NoticeField.COUNTRY},
            :{NoticeField.ESTIMATED_VALUE}, :{NoticeField.CURRENCY}, :{NoticeField.ESTIMATED_VALUE_EUR},
            :{NoticeField.DESCRIPTION}, :{NoticeField.CPV}, :{NoticeField.SOURCE_NAME}
        )
        """
        with self._get_connection() as con:
            con.executemany(query, notices)
            logger.info(f"Database updated: {con.total_changes} rows affected.")

    def get_notice_count(self) -> int:
        """Returns the total number of notices stored in the database.

        Returns:
            An integer count of all rows in the notices table.
        """
        query = f"SELECT COUNT(*) FROM {StorageConfig.DB_TABLE_NOTICES}"
        with self._get_connection() as con:
            return cast(int, con.execute(query).fetchone()[0])

    def fetch_all_notices(self) -> list[dict]:
        """Returns all notices stored in the database.

        Returns:
            A list of all notice rows as plain dictionaries.
        """
        with self._get_connection() as con:
            rows = con.execute(
                f"SELECT * FROM {StorageConfig.DB_TABLE_NOTICES}"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_all_notices_for_nlp(self) -> list[dict]:
        """Returns a lightweight projection of notices for NLP processing.

        Fetches only the fields relevant to text analysis — ID, title,
        and description — to minimize memory usage during embedding generation.

        Returns:
            A list of dicts containing only id, title, and description keys.
        """
        with self._get_connection() as con:
            rows = con.execute(
                f"SELECT {NoticeField.ID}, {NoticeField.TITLE}, {NoticeField.DESCRIPTION} "
                f"FROM {StorageConfig.DB_TABLE_NOTICES}"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_existing_ids(self, id_list: list[str]) -> list[str]:
        """Returns the subset of IDs that already exist in the database.

        Used by the pipeline deduplication step to avoid reprocessing
        notices that have already been stored.

        Args:
            id_list: List of notice IDs to check against the database.

        Returns:
            A list of IDs from id_list that are already present in storage.
        """
        if not id_list:
            return []
        placeholders = ",".join("?" for _ in id_list)
        query = f"SELECT {NoticeField.ID} FROM {StorageConfig.DB_TABLE_NOTICES} WHERE {NoticeField.ID} IN ({placeholders})"
        with self._get_connection() as con:
            result = con.execute(query, id_list).fetchall()
        return [row[0] for row in result]

    def get_country_stats(self, ids: list[str] | None = None) -> list[dict]:
        """Returns notice counts grouped by country.

        When IDs are provided, restricts the aggregation to that subset.
        Used by the dashboard to power the geographic bubble map.

        Args:
            ids: Optional list of notice IDs to restrict the aggregation.
                If None, aggregates across all stored notices.

        Returns:
            A list of dicts with 'country' and 'total_notices' keys,
            sorted by the database's natural order.
        """
        if not ids:
            query = f"""
                SELECT {NoticeField.COUNTRY}, COUNT({NoticeField.ID}) as total_notices
                FROM {StorageConfig.DB_TABLE_NOTICES}
                GROUP BY {NoticeField.COUNTRY}
            """
            with self._get_connection() as con:
                result = con.execute(query).fetchall()
            return [dict(row) for row in result]

        placeholders = ",".join("?" for _ in ids)
        query = f"""
            SELECT {NoticeField.COUNTRY}, COUNT({NoticeField.ID}) as total_notices
            FROM {StorageConfig.DB_TABLE_NOTICES} WHERE {NoticeField.ID} IN ({placeholders})
            GROUP BY {NoticeField.COUNTRY}
        """
        with self._get_connection() as con:
            result = con.execute(query, ids).fetchall()
        return [dict(row) for row in result]

    def get_downloaded_dates(self) -> set[str]:
        """Returns all publication dates present in the notices table.

        Distinct from get_fetched_dates — this reflects dates for which
        notices actually exist, not just dates that were queried.

        Returns:
            A set of date strings in YYYYMMDD format.
        """
        query = f"SELECT DISTINCT {NoticeField.PUB_DATE} FROM {StorageConfig.DB_TABLE_NOTICES}"
        with self._get_connection() as con:
            result = con.execute(query).fetchall()
        return {row[0] for row in result if row[0]}

    def mark_date_as_fetched(self, date_str: str) -> None:
        """Records that a date has been queried from the API.

        Uses INSERT OR IGNORE to make this operation idempotent.
        A date is marked even if no notices were found, preventing
        redundant API calls on subsequent pipeline runs.

        Args:
            date_str: The queried date in YYYYMMDD format.
        """
        with self._get_connection() as con:
            con.execute(
                f"INSERT OR IGNORE INTO {StorageConfig.DB_TABLE_FETCHED_DATES} "
                f"({StorageConfig.FETCHED_DATES_COLUMN}) VALUES (?)",
                (date_str,),
            )

    def get_fetched_dates(self) -> set[str]:
        """Returns all dates that have previously been queried from the API.

        Used by the dashboard to determine which dates still need
        to be downloaded before displaying results.

        Returns:
            A set of date strings in YYYYMMDD format.
        """
        with self._get_connection() as con:
            rows = con.execute(
                f"SELECT {StorageConfig.FETCHED_DATES_COLUMN} FROM {StorageConfig.DB_TABLE_FETCHED_DATES}"
            ).fetchall()
        return {row[0] for row in rows}

    def get_notices_by_ids(self, ids: list[str]) -> list[dict]:
        """Fetches full notice records for the given list of IDs.

        Used by the search service to hydrate semantic search results
        with the full notice payload after ChromaDB returns matching IDs.

        Args:
            ids: List of notice IDs to retrieve.

        Returns:
            A list of full notice dictionaries matching the provided IDs.
        """
        placeholders = ",".join("?" for _ in ids)
        query = f"SELECT * FROM {StorageConfig.DB_TABLE_NOTICES} WHERE {NoticeField.ID} IN ({placeholders})"
        with self._get_connection() as con:
            rows = con.execute(query, ids).fetchall()
        return [dict(row) for row in rows]

    def get_filtered_ids(
        self, cpv_codes: list[str] | None, start_date: str | None, end_date: str | None
    ) -> list[str]:
        """Returns notice IDs matching the provided hard filters.

        At least one filter must be set — if all are None, returns empty list.
        CPV matching is inclusive: a notice passes if it contains at least one
        of the provided codes. Date range is inclusive on both ends.

        Args:
            cpv_codes: List of 8-digit CPV codes to filter on. None skips this filter.
            start_date: Start of publication date range in YYYYMMDD format. Requires end_date.
            end_date: End of publication date range in YYYYMMDD format. Requires start_date.

        Returns:
            List of matching notice IDs.
        """
        if cpv_codes is None and start_date is None and end_date is None:
            return []
        conditions = []
        params = []
        if cpv_codes is not None:
            cpv_conditions = " OR ".join(f"{NoticeField.CPV} LIKE ?" for _ in cpv_codes)
            conditions.append(f"({cpv_conditions})")
            params.extend([f"%{code}%" for code in cpv_codes])

        if start_date is not None and end_date is not None:
            date_condition = f"{NoticeField.PUB_DATE} BETWEEN ? AND ?"
            conditions.append(date_condition)
            params.extend([start_date, end_date])
        if not conditions:
            return []
        where_clause = " AND ".join(conditions)

        query = f"SELECT {NoticeField.ID} FROM {StorageConfig.DB_TABLE_NOTICES} WHERE {where_clause}"

        with self._get_connection() as con:
            rows = con.execute(query, params).fetchall()
        return [row[0] for row in rows]

    def save_alert(self, alert: dict) -> None:
        """Persists a new email alert configuration.

        Args:
            alert: Dict with keys matching AlertField values.
        """
        query = f"""
        INSERT INTO {StorageConfig.DB_TABLE_ALERTS} (
            {AlertField.ID}, {AlertField.EMAIL}, {AlertField.QUERY},
            {AlertField.CPV_CODES}, {AlertField.THRESHOLD},
            {AlertField.SEND_DAYS}, {AlertField.LAST_SENT}
        ) VALUES (
            :{AlertField.ID}, :{AlertField.EMAIL}, :{AlertField.QUERY},
            :{AlertField.CPV_CODES}, :{AlertField.THRESHOLD},
            :{AlertField.SEND_DAYS}, NULL
        )
        """
        with self._get_connection() as con:
            con.execute(query, alert)

    def get_all_alerts(self) -> list[dict]:
        """Returns all saved email alert configurations.

        Returns:
            List of alert dicts with all fields.
        """
        with self._get_connection() as con:
            rows = con.execute(
                f"SELECT * FROM {StorageConfig.DB_TABLE_ALERTS}"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_todays_alerts(self) -> list[dict]:
        """Returns alerts scheduled to fire today.

        An alert fires when today's weekday abbreviation is in its
        send_days field and it has not already been sent today.

        Returns:
            List of alert dicts scheduled for today.
        """
        today_str = date.today().strftime("%Y%m%d")
        today_day = date.today().strftime("%a").upper()
        alerts = self.get_all_alerts()
        return [
            a
            for a in alerts
            if today_day in a[AlertField.SEND_DAYS].split(",")
            and a[AlertField.LAST_SENT] != today_str
        ]

    def delete_alert(self, alert_id: str) -> None:
        """Deletes an alert by its ID.

        Args:
            alert_id: UUID of the alert to delete.
        """
        with self._get_connection() as con:
            con.execute(
                f"DELETE FROM {StorageConfig.DB_TABLE_ALERTS} WHERE {AlertField.ID} = ?",
                (alert_id,),
            )

    def update_alert(self, alert_id: str, updates: dict) -> None:
        """Updates fields of an existing alert.

        Args:
            alert_id: UUID of the alert to update.
            updates: Dict of AlertField keys to new values.
        """
        fields = ", ".join(f"{k} = :{k}" for k in updates)
        updates[AlertField.ID] = alert_id
        with self._get_connection() as con:
            con.execute(
                f"UPDATE {StorageConfig.DB_TABLE_ALERTS} SET {fields} WHERE {AlertField.ID} = :id",
                updates,
            )

    def mark_alert_sent(self, alert_id: str) -> None:
        """Records today as the last send date for an alert.

        Args:
            alert_id: UUID of the alert to mark as sent.
        """
        today_str = date.today().strftime("%Y%m%d")
        with self._get_connection() as con:
            con.execute(
                f"UPDATE {StorageConfig.DB_TABLE_ALERTS} "
                f"SET {AlertField.LAST_SENT} = ? WHERE {AlertField.ID} = ?",
                (today_str, alert_id),
            )

    def save_profile(self, profile: dict) -> None:
        """Persists a new company profile.

        Args:
            profile: Dict with keys matching ProfileField values.
                Keywords, negative_keywords, preferred_countries and
                cpv_codes should be JSON-serialized lists.
        """
        query = f"""
        INSERT INTO {StorageConfig.DB_TABLE_PROFILES} (
            {ProfileField.ID}, {ProfileField.NAME}, {ProfileField.KEYWORDS},
            {ProfileField.NEGATIVE_KEYWORDS}, {ProfileField.PREFERRED_COUNTRIES},
            {ProfileField.CPV_CODES}, {ProfileField.CREATED_AT}
        ) VALUES (
            :{ProfileField.ID}, :{ProfileField.NAME}, :{ProfileField.KEYWORDS},
            :{ProfileField.NEGATIVE_KEYWORDS}, :{ProfileField.PREFERRED_COUNTRIES},
            :{ProfileField.CPV_CODES}, :{ProfileField.CREATED_AT}
        )
        """
        with self._get_connection() as con:
            con.execute(query, profile)

    def get_all_profiles(self) -> list[dict]:
        """Returns all saved company profiles.

        Returns:
            List of profile dicts with all fields.
        """
        with self._get_connection() as con:
            rows = con.execute(
                f"SELECT * FROM {StorageConfig.DB_TABLE_PROFILES}"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_profile_by_id(self, profile_id: str) -> dict | None:
        """Returns a single profile by ID.

        Args:
            profile_id: UUID of the profile to retrieve.

        Returns:
            Profile dict or None if not found.
        """
        with self._get_connection() as con:
            row = con.execute(
                f"SELECT * FROM {StorageConfig.DB_TABLE_PROFILES} "
                f"WHERE {ProfileField.ID} = ?",
                (profile_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_profile(self, profile_id: str, updates: dict) -> None:
        """Updates fields of an existing profile.

        Args:
            profile_id: UUID of the profile to update.
            updates: Dict of ProfileField keys to new values.
        """
        fields = ", ".join(f"{k} = :{k}" for k in updates)
        updates[ProfileField.ID] = profile_id
        with self._get_connection() as con:
            con.execute(
                f"UPDATE {StorageConfig.DB_TABLE_PROFILES} "
                f"SET {fields} WHERE {ProfileField.ID} = :id",
                updates,
            )

    def delete_profile(self, profile_id: str) -> None:
        """Deletes a company profile by ID.

        Args:
            profile_id: UUID of the profile to delete.
        """
        with self._get_connection() as con:
            con.execute(
                f"DELETE FROM {StorageConfig.DB_TABLE_PROFILES} "
                f"WHERE {ProfileField.ID} = ?",
                (profile_id,),
            )
