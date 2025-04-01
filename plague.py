import discord
import requests
import os

from dotenv import load_dotenv
from distance import levenshtein
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

intents=discord.Intents.default()
intents.message_content=True
bot=commands.Bot(command_prefix='plague!', intents=intents)

@bot.event
async def on_ready(): 
    await bot.change_presence(activity=discord.Game("analyze DBD stats."))
    list_serv=[]
    for serv in bot.guilds:
        list_serv.append(serv)
    print(f"Le Bot {bot.user} est connecté. Il est présent dans {len(list_serv)} serveurs.")
    await bot.tree.sync()

@bot.event
async def on_message(message: discord.Message):
    if message.author==bot.user:
        return
    await bot.process_commands(message)

#DEFS
load_dotenv("keys.env")
token=os.getenv("TOKEN")

def tier_color(tier: str):
    if tier=="F":
        return 0xFFFFFF
    elif tier=="D":
        return 0xE4080A
    elif tier=="C":
        return 0xFFDE59
    elif tier=="B":
        return 0x5DE2E7
    elif tier=="A":
        return 0x7DDA58
    else:
        return 0xCC6CE7

def url_parser(lien: str):
    return lien.replace(" ", "%20")

#COMMANDS
@bot.tree.command(
    name="getperkrating",
    description="Getting informations about a perk."
)
@app_commands.describe(
    perk="The name of the perk you want informations about.",
    choice="Is it a survivor or a killer perk ?"
)
@app_commands.choices(
    choice=[
        Choice(
            name="Killer",
            value="Killer"
        ),
        Choice(
            name="Survivor",
            value="Survivor"
        )
    ]
)
async def getperkrating(
    interaction: discord.Interaction,
    perk: str,
    choice: str
):
    await interaction.response.defer()
    data=requests.get(f"https://dennisreep.nl/dbd/api/v3/get{choice}PerkData").json()["Perks"]
    perk_most="None"
    i=0
    index=0
    for info in data:
        if levenshtein(info["PerkName"], perk)<levenshtein(perk_most, perk):
            perk_most=info["PerkName"]
            index=i
        i+=1
    final=data[index]
    e=discord.Embed(
        title=perk_most,
        description=f"Informations about {perk_most}",
        color=tier_color(final["Tier"])
    )
    e.set_thumbnail(
        url=url_parser(final["Image"])
    )
    e.add_field(
        name="Character",
        value=final[choice]
    )
    e.add_field(
        name="Rating",
        value=f"{final['Rating']}/5, out of {final['Ratings']} ratings."
    )
    e.add_field(
        name="Tier",
        value=final["Tier"]
    )
    e.set_footer(
        text=f"Command made by {interaction.user}",
        icon_url=interaction.user.avatar
    )
    await interaction.followup.send(embed=e)

@bot.tree.command(
    name="getkillerbuild",
    description="Gives the greatest build for a specified killer."
)
@app_commands.describe(
    killer="The killer you want.",
    start="The number you want to start to (default: 1)"
)
async def getkillerbuild(
    interaction: discord.Interaction,
    killer: str,
    start: int = None
):
    await interaction.response.defer()
    data_killer=requests.get("https://dennisreep.nl/dbd/api/v3/getKillerData").json()["Killers"]
    if start==None:
        start=0
    else:
        start=start-1
    killer_most="None"
    index=0
    i=0
    for killer_info in data_killer:
        if levenshtein(killer_info["KillerName"], killer)<levenshtein(killer_most, killer):
            index=i
            killer_most=killer_info["KillerName"]
        i+=1
    killer_most_data=data_killer[index]
    data=requests.get(f"https://dennisreep.nl/dbd/api/v3/getKillerData/?killer={killer_most}").json()["Killers"]
    embed=discord.Embed(
        title=killer_most,
        description=f"{killer_most}'s build. Starting from : {start+1}"
    )
    embed.set_thumbnail(
        url=url_parser(killer_most_data["Image"])
    )
    embed.set_footer(
        text=f"Command made by {interaction.user}",
        icon_url=interaction.user.avatar
    )
    es=[embed]
    for i in range(start, start+4):
        a=e=discord.Embed(
            title=data[i]["PerkName"],
            description=f"Killer : {data[i]['PerkKiller']}",
            color=tier_color(data[i]["Tier"])
        )
        e.set_thumbnail(
            url=url_parser(data[i]["PerkIcon"])
        )
        e.add_field(
            name="Name",
            value=data[i]["PerkName"]
        )
        e.add_field(
            name="Rating",
            value=f"{data[i]['Rating']}/5, out of {data[i]['Ratings']} ratings."
        )
        e.add_field(
            name="Tier",
            value=data[i]["Tier"]
        )
        es.append(a)
    await interaction.followup.send(embeds=es)

@bot.tree.command(
    name="getkillerrating",
    description="Get informations about a killer"
)
@app_commands.describe(
    killer="The killer you want informations about."
)
async def getkillerrating(
    interaction: discord.Interaction,
    killer: str
):
    await interaction.response.defer()
    data=requests.get("https://dennisreep.nl/dbd/api/v3/getKillerData").json()["Killers"]
    killer_most="None"
    i=0
    index=0
    for info in data:
        if levenshtein(info["KillerName"], killer)<levenshtein(killer_most, killer):
            killer_most=info["KillerName"]
            index=i
        i+=1
    final=data[index]
    e=discord.Embed(
        title=killer_most,
        description=f"Informations about {killer_most}",
        color=tier_color(final["Tier"])
    )
    e.set_thumbnail(
        url=url_parser(final["Image"])
    )
    e.add_field(
        name="Killer",
        value=final["KillerName"]
    )
    e.add_field(
        name="Rating",
        value=f"{final['Rating']}/5, out of {final['Ratings']} ratings."
    )
    e.add_field(
        name="Tier",
        value=final["Tier"]
    )
    e.set_footer(
        text=f"Command made by {interaction.user}",
        icon_url=interaction.user.avatar
    )
    await interaction.followup.send(embed=e)

@bot.tree.command(
    name="gethelp",
    description="Get the list of all commands."
)
async def gethelp(
    interaction: discord.Interaction
):
    e=discord.Embed(
        title="Help",
        description=f"{bot.user}'s commands. \n() : required \n[] : optional."
    )
    e.add_field(
        name="/getperkrating (perk)",
        value="Gives you the rating of a specified perk."
    )
    e.add_field(
        name="/getkillerbuild (killer) [start]",
        value="Get the build that most of the players use for a killer. The start variable is the index of the starting perk, for instance, if start = 5, it will give the 4 perks following the fifth perk."
    )
    e.add_field(
        name="/getkillerrating (killer)",
        value="Gives you the rating of a specified killer according to users."
    )
    e.set_footer(
        text=f"Command made by {interaction.user}",
        icon_url=interaction.user.avatar
    )
    await interaction.response.send_message(embed=e)

bot.run(token)