### `conferences`
| Key | Column | Type | Constraints |
| :--- | :--- | :--- | :--- |
| **PK** | id | INTEGER | NOT NULL |
| AK | name | TEXT | NOT NULL |
| AK | abbreviation | TEXT | NOT NULL |

### `teams`
| Key | Column | Type | Constraints |
| :--- | :--- | :--- | :--- |
| **PK** | id | INTEGER | NOT NULL |
| FK | conference_id | INTEGER | NOT NULL |
| | city | TEXT | NOT NULL |
| | name | TEXT | NOT NULL |
| | full_name | TEXT | NOT NULL |
| | abbreviation | TEXT | NOT NULL |

### `standings`
| Key | Column | Type | Constraints |
| :--- | :--- | :--- | :--- |
| **PK** | id | INTEGER | AUTOINCREMENT NOT NULL |
| FK | team_id | INTEGER | NOT NULL |
| FK | conference_id | INTEGER | NOT NULL |
| | season | INTEGER | NOT NULL |
| | snapshot_date | TEXT | NOT NULL |
| | wins | INTEGER | |
| | losses | INTEGER | |
| | win_percentage | REAL | |
| | games_behind | REAL | |
| | home_record | TEXT | |
| | away_record | TEXT | |
| | conference_record | TEXT | |