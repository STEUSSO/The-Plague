"""
Logging and Statistics Tracker for The Plague Discord Bot.
Logs all command interactions to the console and records them into SQLite.
"""
import os
import json
import sqlite3
import datetime
from typing import Optional, Dict, Any
import discord

DATA_DIR = os.getenv("STATS_DATA_DIR", "data")
if DATA_DIR and not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        DATA_DIR = ""

DB_PATH = os.path.join(DATA_DIR, "stats.db") if DATA_DIR else "stats.db"

def init_db():
    """Initializes the SQLite stats database table if it doesn't exist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                command_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                guild_id INTEGER,
                guild_name TEXT,
                channel_id INTEGER,
                args_json TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_command_logs_cmd ON command_logs(command_name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_command_logs_user ON command_logs(user_id)
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ [StatsDB] Failed to initialize database: {e}")

def log_command(interaction: discord.Interaction, command_name: str, **kwargs):
    """
    Prints a detailed command log to the console and records it in SQLite.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    user = interaction.user
    user_id = user.id
    username = f"{user.name}" if hasattr(user, "name") else str(user)

    guild = interaction.guild
    guild_id = guild.id if guild else None
    guild_name = guild.name if guild else "Direct Message (DM)"
    channel_id = interaction.channel_id

    # Format arguments
    clean_args = {k: v for k, v in kwargs.items() if v is not None}
    args_str = " ".join([f"{k}={repr(v)}" for k, v in clean_args.items()])
    args_json = json.dumps(clean_args, ensure_ascii=False)

    # 1. Print formatted log to console
    print(f"📊 [COMMAND] {timestamp_str} | User: {username} ({user_id}) | Server: {guild_name} ({guild_id}) | /{command_name} {args_str}".strip())

    # 2. Record to SQLite database for future dashboard
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO command_logs (timestamp, command_name, user_id, username, guild_id, guild_name, channel_id, args_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp_str, command_name, user_id, username, guild_id, guild_name, channel_id, args_json))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ [StatsDB] Error saving log: {e}")

def get_stats_summary() -> Dict[str, Any]:
    """Returns quick aggregated statistics from SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM command_logs")
        total_commands = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM command_logs")
        unique_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT guild_id) FROM command_logs WHERE guild_id IS NOT NULL")
        unique_guilds = cursor.fetchone()[0]

        cursor.execute("""
            SELECT command_name, COUNT(*) as cnt 
            FROM command_logs 
            GROUP BY command_name 
            ORDER BY cnt DESC 
            LIMIT 5
        """)
        top_commands = cursor.fetchall()
        conn.close()
        return {
            "total_commands": total_commands,
            "unique_users": unique_users,
            "unique_guilds": unique_guilds,
            "top_commands": top_commands,
        }
    except Exception as e:
        return {"error": str(e)}

# Auto-initialize DB on import
init_db()
