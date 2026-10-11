"""
The Plague — Modern Dead by Daylight Discord Assistant.
Redesigned with Discord Slash Commands, Autocomplete, Interactive UI, and Pillow HUD rendering.
Fully internationalized in English. Compatible with Python 3.12, 3.13, 3.14+.
"""
import os
import random
import asyncio
from typing import Optional, List
import discord
from discord import app_commands, ui
from discord.app_commands import Choice
from discord.ext import commands
from dotenv import load_dotenv

from constants import (
    KILLERS_DB,
    TIER_COLORS,
    THEME_COLOR,
    TOPGG_VOTE_URL,
    resolve_killer,
    normalize_text,
    rating_bar
)
from api import dbd_client
from card_generator import generate_killer_build_card, generate_randomizer_card
from ui_views import KillerBuildView, RandomizerView, TierListView
from db_logger import log_command, get_stats_summary

# Try loading from any potential env file location
for env_file in [".env", "keys.env", "/app/.env", "/app/keys.env", "../.env", "../keys.env"]:
    if os.path.exists(env_file):
        load_dotenv(env_file, override=False)

# Support any standard naming convention (case-insensitive)
TOKEN = (
    os.getenv("TOKEN")
    or os.getenv("DISCORD_TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("token")
    or os.getenv("discord_token")
    or os.getenv("bot_token")
)

if TOKEN:
    TOKEN = TOKEN.strip().strip('"').strip("'")
else:
    print("[ERROR] Bot token not found!")
    print(f"[DEBUG] Available environment variable keys in container: {list(os.environ.keys())}")
    print("[HINT] In Docker, provide your token via: -e TOKEN='your_token' or in your panel's 'Environment Variables' tab.")

# Discord Client Setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="plague!",
    intents=intents,
    help_command=None
)

# ---------------------------------------------------------
# BOT EVENTS & LIFECYCLE
# ---------------------------------------------------------
@bot.event
async def on_ready():
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name="DBD Builds & Stats | /killerbuild"
    )
    await bot.change_presence(activity=activity)

    guild_count = len(bot.guilds)
    print(f"✨ [The Plague] Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"🌐 [The Plague] Connected to {guild_count} server(s).")

    # Warm up perk and killer cache in background
    asyncio.create_task(warm_up_cache())

    try:
        synced = await bot.tree.sync()
        print(f"🔄 [The Plague] {len(synced)} slash commands successfully synced globally.")
    except Exception as e:
        print(f"❌ [The Plague] Error while syncing slash commands: {e}")

async def warm_up_cache():
    """Pre-loads killer and perk datasets into memory upon bot launch."""
    try:
        await dbd_client.get_all_killers()
        await dbd_client.get_perks("Killer")
        await dbd_client.get_perks("Survivor")
        print("⚡ [The Plague] DBD Dennis Reep data cache successfully pre-warmed.")
    except Exception as e:
        print(f"⚠️ [The Plague] Failed to pre-warm cache: {e}")

@bot.event
async def on_close():
    await dbd_client.close()

# ---------------------------------------------------------
# AUTOCOMPLETE PROVIDERS
# ---------------------------------------------------------
async def killer_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[Choice[str]]:
    """Real-time autocomplete for all 43 killers."""
    query = current.lower().strip()
    choices: List[Choice[str]] = []

    if not query:
        # Default top picks
        top_picks = ["Plague", "Nurse", "Blight", "Shape", "Mastermind", "Good Guy", "Cenobite", "Huntress", "Spirit", "Oni"]
        for k in KILLERS_DB:
            if k["api_name"] in top_picks:
                choices.append(Choice(name=k["display_name"], value=k["api_name"]))
            if len(choices) >= 25:
                break
        return choices

    norm_query = normalize_text(query)

    for k in KILLERS_DB:
        matches = (
            norm_query in normalize_text(k["display_name"])
            or norm_query in normalize_text(k["api_name"])
            or any(norm_query in normalize_text(a) for a in k.get("aliases", []))
        )
        if matches:
            choices.append(Choice(name=k["display_name"], value=k["api_name"]))
            if len(choices) >= 25:
                break

    return choices

async def perk_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> List[Choice[str]]:
    """Real-time autocomplete for Killer and Survivor perks."""
    query = current.lower().strip()
    if not query:
        return [
            Choice(name="Corrupt Intervention (Killer - Plague)", value="Corrupt Intervention"),
            Choice(name="Pop Goes The Weasel (Killer - Clown)", value="Pop Goes The Weasel"),
            Choice(name="Scourge Hook: Pain Resonance (Killer - Artist)", value="Scourge Hook: Pain Resonance"),
            Choice(name="Windows Of Opportunity (Survivor - Kate)", value="Windows Of Opportunity"),
            Choice(name="Adrenaline (Survivor - Meg)", value="Adrenaline"),
            Choice(name="Lithe (Survivor - Feng)", value="Lithe"),
            Choice(name="Dead Hard (Survivor - David)", value="Dead Hard"),
        ]

    norm_query = normalize_text(query)
    all_perks = await dbd_client.get_all_perks_combined()
    choices: List[Choice[str]] = []

    for p in all_perks:
        p_name = p.get("PerkName", "")
        if norm_query in normalize_text(p_name):
            role_label = p.get("Role", "Perk")
            tier = p.get("Tier", "?")
            character = p.get("Killer") or p.get("Survivor", "General")
            choices.append(
                Choice(
                    name=f"{p_name} ({role_label} - {character} - Tier {tier})"[:100],
                    value=p_name
                )
            )
            if len(choices) >= 25:
                break

    return choices

# ---------------------------------------------------------
# SLASH COMMANDS
# ---------------------------------------------------------

# 1. KILLER BUILD & RATING (Merged & Upgraded)
@bot.tree.command(
    name="killerbuild",
    description="Retrieve the meta build and detailed community stats for any killer."
)
@app_commands.describe(
    killer="Killer name (e.g. Plague, Myers, Wesker, Chucky, Trapper...)",
    page="Build page number (default 1, 4 perks per page)"
)
@app_commands.autocomplete(killer=killer_autocomplete)
async def killerbuild_cmd(
    interaction: discord.Interaction,
    killer: str,
    page: Optional[int] = 1
):
    log_command(interaction, "killerbuild", killer=killer, page=page)
    await interaction.response.defer()

    resolved = resolve_killer(killer)
    if not resolved:
        await interaction.followup.send(
            f"❌ Sorry, could not recognize the killer **'{killer}'**.\n"
            "💡 *Tip: Use autocomplete suggestions or names like `Plague`, `Myers`, `Wesker`, `Chucky`, `Trapper`.*",
            ephemeral=True
        )
        return

    api_name = resolved["api_name"]
    display_name = resolved["display_name"]

    perks = await dbd_client.get_killer_build(api_name)
    killer_stats = await dbd_client.get_killer_stats(api_name)

    if not perks:
        await interaction.followup.send(
            f"⚠️ No build data found for **{display_name}**.",
            ephemeral=True
        )
        return

    if not killer_stats:
        killer_stats = {
            "KillerName": api_name,
            "Tier": perks[0].get("Tier", "B"),
            "Rating": 3.5,
            "Ratings": 0,
            "Image": ""
        }

    page_idx = max(0, (page or 1) - 1)
    max_pages = min(4, (len(perks) + 3) // 4)
    if page_idx >= max_pages:
        page_idx = 0

    session = await dbd_client.get_session()
    view = KillerBuildView(
        killer_info=killer_stats,
        all_perks=perks,
        session=session,
        killer_display_name=display_name,
        initial_page=page_idx,
        max_pages=max_pages
    )

    # 10% chance to attach a discreet Top.gg support button
    if random.random() < 0.10:
        view.add_item(
            ui.Button(
                label="Support on Top.gg",
                url=TOPGG_VOTE_URL,
                style=discord.ButtonStyle.link,
                emoji="⭐",
                row=2
            )
        )

    embed, file = await view.get_page_payload()
    await interaction.followup.send(embed=embed, file=file, view=view)


# Alias: /build
@bot.tree.command(
    name="build",
    description="Shortcut for /killerbuild — Get the top meta build for a killer."
)
@app_commands.describe(killer="Killer name", page="Page number")
@app_commands.autocomplete(killer=killer_autocomplete)
async def build_alias(interaction: discord.Interaction, killer: str, page: Optional[int] = 1):
    await killerbuild_cmd.callback(interaction, killer, page)


# Alias: /getkillerbuild (backwards compatibility)
@bot.tree.command(
    name="getkillerbuild",
    description="Legacy command — Displays the killer meta build."
)
@app_commands.describe(killer="Killer name", page="Page number")
@app_commands.autocomplete(killer=killer_autocomplete)
async def getkillerbuild_alias(interaction: discord.Interaction, killer: str, page: Optional[int] = 1):
    await killerbuild_cmd.callback(interaction, killer, page)


# Alias: /getkillerrating (merged with killerbuild as requested)
@bot.tree.command(
    name="getkillerrating",
    description="Get the killer rating, tier, and meta build in a unified view."
)
@app_commands.describe(killer="Killer name to inspect")
@app_commands.autocomplete(killer=killer_autocomplete)
async def getkillerrating_alias(interaction: discord.Interaction, killer: str):
    await killerbuild_cmd.callback(interaction, killer, 1)


# 2. PERK RATING & DETAILS
@bot.tree.command(
    name="perk",
    description="Look up rating, tier, and details of any perk (Killer or Survivor)."
)
@app_commands.describe(
    perk="Perk name (e.g. Corrupt Intervention, Dead Hard, Pain Resonance...)",
    role="Filter by role (optional)"
)
@app_commands.choices(
    role=[
        Choice(name="All / Auto-detect", value="Auto"),
        Choice(name="🗡️ Killer", value="Killer"),
        Choice(name="🏃 Survivor", value="Survivor")
    ]
)
@app_commands.autocomplete(perk=perk_autocomplete)
async def perk_cmd(
    interaction: discord.Interaction,
    perk: str,
    role: Optional[Choice[str]] = None
):
    role_val = role.value if role and role.value != "Auto" else "Auto"
    log_command(interaction, "perk", perk=perk, role=role_val)
    await interaction.response.defer()

    role_filter = role.value if role and role.value != "Auto" else None
    found_perk = await dbd_client.search_perk(perk, role_filter)

    if not found_perk:
        await interaction.followup.send(
            f"❌ Sorry, no perk matching **'{perk}'** was found.\n"
            "💡 *Tip: Use the real-time autocomplete suggestions as you type.*",
            ephemeral=True
        )
        return

    p_name = found_perk.get("PerkName")
    tier = found_perk.get("Tier", "B")
    rating_val = float(found_perk.get("Rating", 0))
    ratings_count = found_perk.get("Ratings", 0)
    perk_role = found_perk.get("Role", "General")
    character = found_perk.get("Killer") or found_perk.get("Survivor", "General / All")
    img_url = found_perk.get("Image") or found_perk.get("PerkIcon")

    color = TIER_COLORS.get(tier, THEME_COLOR)

    embed = discord.Embed(
        title=f"📜 {p_name}",
        description=f"**{perk_role} Perk** • Teachable From: **{character}**",
        color=color
    )

    if img_url:
        embed.set_thumbnail(url=img_url.strip().replace(" ", "%20"))

    embed.add_field(name="🏆 Tier", value=f"**Tier {tier}**", inline=True)
    embed.add_field(name="⭐ Community Rating", value=f"**{rating_val:.2f} / 5.0**", inline=True)
    embed.add_field(name="🗳️ Reviews Count", value=f"**{ratings_count:,}** ratings", inline=True)
    embed.add_field(
        name="📊 Effectiveness Bar",
        value=f"`{rating_bar(rating_val, 5.0, 12)}` ({(rating_val/5.0)*100:.1f}%)",
        inline=False
    )

    embed.set_footer(
        text=f"The Plague • Requested by {interaction.user.display_name}",
        icon_url=interaction.user.display_avatar.url
    )

    # Shortcut button if it's a killer perk
    view = ui.View(timeout=120)
    if perk_role == "Killer" and character != "All":
        resolved_k = resolve_killer(character)
        if resolved_k:
            btn = ui.Button(
                label=f"View {character}'s Build",
                style=discord.ButtonStyle.primary,
                emoji="🗡️"
            )
            async def btn_callback(btn_interaction: discord.Interaction):
                await killerbuild_cmd.callback(btn_interaction, resolved_k["api_name"], 1)
            btn.callback = btn_callback
            view.add_item(btn)

    await interaction.followup.send(embed=embed, view=view if len(view.children) > 0 else None)


# Alias: /getperkrating (legacy compatibility)
@bot.tree.command(
    name="getperkrating",
    description="Legacy command — Look up the rating of a specific perk."
)
@app_commands.describe(
    perk="Perk name",
    choice="Perk role (Killer or Survivor)"
)
@app_commands.choices(
    choice=[
        Choice(name="Killer", value="Killer"),
        Choice(name="Survivor", value="Survivor")
    ]
)
@app_commands.autocomplete(perk=perk_autocomplete)
async def getperkrating_alias(
    interaction: discord.Interaction,
    perk: str,
    choice: Choice[str]
):
    await perk_cmd.callback(interaction, perk, choice)


# 3. RANDOMIZER / ROULETTE (With Custom Loadout Card!)
@bot.tree.command(
    name="randomizer",
    description="Roll a random Dead by Daylight challenge loadout with a custom HUD card and Reroll button!"
)
@app_commands.describe(
    role="Play as Killer or Survivor?",
    killer="Lock a specific killer (optional, killer role only)"
)
@app_commands.choices(
    role=[
        Choice(name="🗡️ Killer", value="Killer"),
        Choice(name="🏃 Survivor", value="Survivor")
    ]
)
@app_commands.autocomplete(killer=killer_autocomplete)
async def randomizer_cmd(
    interaction: discord.Interaction,
    role: Choice[str],
    killer: Optional[str] = None
):
    log_command(interaction, "randomizer", role=role.value, killer=killer)
    await interaction.response.defer()

    is_killer = (role.value == "Killer")
    perks = await dbd_client.get_perks("Killer" if is_killer else "Survivor")
    killers = await dbd_client.get_all_killers() if is_killer else []

    locked_k_info = None
    if is_killer and killer:
        resolved = resolve_killer(killer)
        if resolved:
            locked_k_info = await dbd_client.get_killer_stats(resolved["api_name"])

    session = await dbd_client.get_session()
    view = RandomizerView(
        role=role.value,
        killer_pool=killers,
        perk_pool=perks,
        session=session,
        locked_killer=locked_k_info
    )

    # 10% chance to attach a discreet Top.gg support button
    if random.random() < 0.10:
        view.add_item(
            ui.Button(
                label="Support on Top.gg",
                url=TOPGG_VOTE_URL,
                style=discord.ButtonStyle.link,
                emoji="⭐",
                row=2
            )
        )

    embed, file = await view.get_payload()
    await interaction.followup.send(embed=embed, file=file, view=view)


# Alias: /roulette
@bot.tree.command(
    name="roulette",
    description="Shortcut for /randomizer — Spin a random DBD challenge build."
)
@app_commands.describe(role="Killer or Survivor?")
@app_commands.choices(
    role=[
        Choice(name="🗡️ Killer", value="Killer"),
        Choice(name="🏃 Survivor", value="Survivor")
    ]
)
async def roulette_alias(interaction: discord.Interaction, role: Choice[str]):
    await randomizer_cmd.callback(interaction, role, None)


# 4. SURVIVOR META BUILD
@bot.tree.command(
    name="survivorbuild",
    description="Displays the highest-rated meta build for Survivors with an HD HUD card."
)
async def survivorbuild_cmd(interaction: discord.Interaction):
    log_command(interaction, "survivorbuild")
    await interaction.response.defer()
    all_surv_perks = await dbd_client.get_perks("Survivor")
    top_perks = sorted(all_surv_perks, key=lambda p: float(p.get("Rating", 0)), reverse=True)[:4]

    session = await dbd_client.get_session()
    buf = await generate_randomizer_card(session, "Survivor", top_perks)
    file = discord.File(fp=buf, filename="survivor_meta.png")

    embed = discord.Embed(
        title="🏃 Recommended Survivor Meta Build",
        description="The 4 highest-rated Survivor perks according to community consensus.",
        color=0x5DE2E7
    )

    for i, p in enumerate(top_perks):
        embed.add_field(
            name=f"#{i+1} {p.get('PerkName')}",
            value=f"Tier **{p.get('Tier')}** • ⭐ **{p.get('Rating')}/5**\nTeachable: *{p.get('Survivor')}*",
            inline=True
        )

    embed.set_image(url=f"attachment://{file.filename}")
    embed.set_footer(text="The Plague • Check /perk for in-depth perk analytics.")
    await interaction.followup.send(embed=embed, file=file)


# 5. TIER LIST
@bot.tree.command(
    name="tierlist",
    description="View the official community Tier List for Killers and Survivor Perks."
)
async def tierlist_cmd(interaction: discord.Interaction):
    log_command(interaction, "tierlist")
    await interaction.response.defer()
    killers = await dbd_client.get_all_killers()
    surv_perks = await dbd_client.get_perks("Survivor")

    view = TierListView(killers=killers, surv_perks=surv_perks)
    embed = view.get_embed()
    await interaction.followup.send(embed=embed, view=view)


# 6. HELP COMMAND
@bot.tree.command(
    name="help",
    description="List all commands and features of The Plague."
)
async def help_cmd(interaction: discord.Interaction):
    log_command(interaction, "help")
    embed = discord.Embed(
        title="🩸 The Plague — Dead by Daylight Discord Assistant",
        description=(
            "Welcome to **The Plague**, your ultimate tactical companion for Dead by Daylight!\n"
            "All ratings and builds are synced in real-time with the **Dennis Reep DBD Database**.\n\n"
            "✨ **Key Features:** Real-time autocomplete, HD loadout HUD image generation, "
            "interactive page browsing, and custom challenge roulettes."
        ),
        color=THEME_COLOR
    )

    embed.add_field(
        name="🗡️ `/killerbuild (killer) [page]`",
        value=(
            "Displays the **complete meta build** for a killer with overall tier, rating, "
            "custom HD HUD card, and interactive pagination to browse through all top 16 perks.\n"
            "*(Aliases: `/build`, `/getkillerbuild`, `/getkillerrating`)*"
        ),
        inline=False
    )

    embed.add_field(
        name="📜 `/perk (perk) [role]`",
        value=(
            "Search any perk with instant autocomplete. Displays Tier, 5-star rating, "
            "review count, teachable character, and an effectiveness visual bar.\n"
            "*(Alias: `/getperkrating`)*"
        ),
        inline=False
    )

    embed.add_field(
        name="🎲 `/randomizer (role) [killer]`",
        value=(
            "Generate a random challenge build for you and your friends! "
            "Renders a high-contrast HUD loadout card with a live **Reroll** button.\n"
            "*(Alias: `/roulette`)*"
        ),
        inline=False
    )

    embed.add_field(
        name="🏃 `/survivorbuild`",
        value="Showcase the top-ranked Survivor meta build with community ratings and custom HUD card.",
        inline=False
    )

    embed.add_field(
        name="🏆 `/tierlist`",
        value="Interactive community tier list comparing all 43 killers and top survivor perks.",
        inline=False
    )

    embed.add_field(
        name="⭐ `/vote`",
        value="Support the solo developer by casting a free vote on Top.gg (takes 10 seconds!).",
        inline=False
    )

    embed.set_footer(
        text=f"The Plague Bot • In {len(bot.guilds)} servers",
        icon_url=bot.user.display_avatar.url if bot.user else None
    )

    view = ui.View(timeout=None)
    view.add_item(
        ui.Button(
            label="Vote on Top.gg (Free) ⭐",
            url=TOPGG_VOTE_URL,
            style=discord.ButtonStyle.link
        )
    )

    await interaction.response.send_message(embed=embed, view=view)


# Alias: /gethelp
@bot.tree.command(
    name="gethelp",
    description="Legacy command — Displays the bot help menu."
)
async def gethelp_alias(interaction: discord.Interaction):
    await help_cmd.callback(interaction)


# 7. VOTE COMMAND (Heartfelt & Supporting Solo Dev)
@bot.tree.command(
    name="vote",
    description="Support the solo creator of The Plague by casting a free vote on Top.gg!"
)
async def vote_cmd(interaction: discord.Interaction):
    log_command(interaction, "vote")
    embed = discord.Embed(
        title="🩸 Support The Plague — Vote on Top.gg",
        description=(
            "Hello Fog travelers! 🖤\n\n"
            "**The Plague** is a 100% free and open-source passion project developed entirely by a single person "
            "for the Dead by Daylight community. There are no paywalls, no paid tiers, and no ads.\n\n"
            "If this bot has helped you find great builds, survive grueling trials, or enjoy roulette challenges with your friends, "
            "taking **10 seconds** to drop a free vote on **Top.gg** is the biggest support you can give!\n\n"
            "It gives the bot visibility on Discord, keeps server hosting alive, and motivates continuous updates.\n\n"
            "Every single vote means the world to me. Thank you for your support in the Fog! 🩸"
        ),
        color=THEME_COLOR
    )
    embed.set_thumbnail(url="https://www.dennisreep.nl/dbd/images/Killers/Plague.webp")
    embed.add_field(
        name="🌟 Why Vote?",
        value=(
            "• Completely free (takes 2 clicks and ~10 seconds).\n"
            "• Helps new players discover the bot.\n"
            "• You can vote once every **12 hours**!"
        ),
        inline=False
    )
    embed.set_footer(
        text="Thank you for supporting independent developers!",
        icon_url=interaction.user.display_avatar.url
    )

    view = ui.View(timeout=None)
    view.add_item(
        ui.Button(
            label="Vote for The Plague on Top.gg (Free)",
            url=TOPGG_VOTE_URL,
            style=discord.ButtonStyle.link,
            emoji="⭐"
        )
    )
    await interaction.response.send_message(embed=embed, view=view)


# 8. STATS COMMAND (Real-time Usage & Top Commands)
@bot.tree.command(
    name="stats",
    description="Display real-time command usage and community metrics for The Plague."
)
async def stats_cmd(interaction: discord.Interaction):
    log_command(interaction, "stats")
    await interaction.response.defer()

    stats = get_stats_summary()
    embed = discord.Embed(
        title="📊 The Plague — Bot Analytics",
        description="Live statistics recorded from Discord slash command interactions.",
        color=THEME_COLOR
    )
    embed.add_field(name="🌐 Servers", value=f"**{len(bot.guilds):,}** guilds", inline=True)
    embed.add_field(name="⚡ Commands Executed", value=f"**{stats.get('total_commands', 0):,}** calls", inline=True)
    embed.add_field(name="👥 Unique Users", value=f"**{stats.get('unique_users', 0):,}** users", inline=True)

    top_cmds = stats.get("top_commands", [])
    if top_cmds:
        top_str = "\n".join([f"• `/{cmd}` : **{cnt:,}** executions" for cmd, cnt in top_cmds])
        embed.add_field(name="🔥 Top Commands", value=top_str, inline=False)

    embed.set_footer(text="The Plague Analytics • Persistent SQLite tracking")
    await interaction.followup.send(embed=embed)


# ---------------------------------------------------------
# GLOBAL ERROR HANDLER
# ---------------------------------------------------------
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):
    print(f"❌ [Command Error] {error}")
    err_msg = "An error occurred while executing this command. Please try again later."
    if interaction.response.is_done():
        await interaction.followup.send(f"⚠️ {err_msg}", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ {err_msg}", ephemeral=True)

# ---------------------------------------------------------
# START BOT
# ---------------------------------------------------------
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("[FATAL] Cannot start bot: Missing TOKEN in keys.env or .env file.")