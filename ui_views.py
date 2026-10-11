"""
Discord UI components (Views, Buttons, Selects) for The Plague DBD Bot.
100% in English, featuring interactive pagination, perk inspection, and reroll mechanics.
"""
import random
from typing import List, Dict, Any, Optional, Tuple
import discord
from discord import ui
from constants import TIER_COLORS, rating_bar
from card_generator import generate_killer_build_card, generate_randomizer_card

class PerkSelect(ui.Select):
    """Dropdown allowing users to inspect any perk on the current page."""
    def __init__(self, perks: List[Dict[str, Any]]):
        options = []
        for i, p in enumerate(perks[:4]):
            p_name = p.get("PerkName", f"Perk {i+1}")
            tier = p.get("Tier", "?")
            rating = p.get("Rating", 0)
            origin = p.get("PerkKiller") or p.get("Killer") or p.get("Survivor", "General")
            options.append(
                discord.SelectOption(
                    label=p_name[:100],
                    description=f"Tier {tier} • Rating: {rating}/5 • From: {origin}"[:100],
                    value=str(i),
                    emoji="💎" if tier in ["S", "A"] else "💠"
                )
            )
        super().__init__(
            placeholder="🔍 Inspect a perk in detail...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        view: KillerBuildView = self.view
        perk = view.current_page_perks[idx]

        tier = perk.get("Tier", "B")
        embed = discord.Embed(
            title=f"📜 Perk Details: {perk.get('PerkName')}",
            description=f"Comprehensive community statistics for **{view.killer_name}**.",
            color=TIER_COLORS.get(tier, 0x8A2BE2)
        )
        icon_url = perk.get("PerkIcon") or perk.get("Image")
        if icon_url:
            embed.set_thumbnail(url=icon_url.strip().replace(" ", "%20"))

        rating_val = float(perk.get("Rating", 0))
        ratings_cnt = perk.get("Ratings", 0)
        origin = perk.get("PerkKiller") or perk.get("Killer") or perk.get("Survivor", "General")

        embed.add_field(name="🏆 Tier", value=f"**Tier {tier}**", inline=True)
        embed.add_field(
            name="⭐ Effectiveness Rating",
            value=f"**{rating_val:.2f} / 5.0**\n`{rating_bar(rating_val)}`",
            inline=True
        )
        embed.add_field(name="🗳️ Community Votes", value=f"**{ratings_cnt:,}** ratings", inline=True)
        embed.add_field(name="👤 Teachable From", value=f"**{origin}**", inline=True)
        embed.add_field(
            name="📊 Rank in this Build",
            value=f"**#{view.page * 4 + idx + 1}** of {len(view.all_perks)} perks",
            inline=True
        )

        embed.set_footer(
            text="The Plague • Powered by Dennis Reep DBD Database",
            icon_url=interaction.user.display_avatar.url
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class KillerBuildView(ui.View):
    """Interactive view for browsing killer builds with card rendering and pagination."""
    def __init__(
        self,
        killer_info: Dict[str, Any],
        all_perks: List[Dict[str, Any]],
        session,
        killer_display_name: str,
        initial_page: int = 0,
        max_pages: int = 4
    ):
        super().__init__(timeout=180)
        self.killer_info = killer_info
        self.all_perks = all_perks
        self.session = session
        self.killer_name = killer_display_name
        self.page = initial_page
        self.max_pages = min(max_pages, (len(all_perks) + 3) // 4)
        self.current_page_perks: List[Dict[str, Any]] = []

        self._refresh_components()

    def _refresh_components(self):
        start = self.page * 4
        self.current_page_perks = self.all_perks[start:start+4]

        # Update button states
        self.btn_first.disabled = (self.page == 0)
        self.btn_prev.disabled = (self.page == 0)
        self.btn_next.disabled = (self.page >= self.max_pages - 1)

        # Rebuild select menu
        for child in list(self.children):
            if isinstance(child, PerkSelect):
                self.remove_item(child)
        if self.current_page_perks:
            self.add_item(PerkSelect(self.current_page_perks))

    async def get_page_payload(self) -> Tuple[discord.Embed, discord.File]:
        """Generates embed and file for the current page."""
        tier = self.killer_info.get("Tier", "B")
        rating = float(self.killer_info.get("Rating", 0))
        ratings_cnt = self.killer_info.get("Ratings", 0)
        k_image = self.killer_info.get("Image", "")

        # Generate image card
        buf = await generate_killer_build_card(
            self.session,
            self.killer_name,
            k_image,
            tier,
            rating,
            self.current_page_perks,
            page_num=self.page + 1,
            total_pages=self.max_pages
        )
        file = discord.File(fp=buf, filename=f"build_{self.killer_info.get('KillerName', 'killer')}.png")

        # Build Embed
        color = TIER_COLORS.get(tier, 0x8A2BE2)
        embed = discord.Embed(
            title=f"🩸 {self.killer_name} — Build & Statistics",
            description=(
                f"**Overall Killer Rating:** ⭐ **{rating:.2f}/5.0** (`{rating_bar(rating)}`)\n"
                f"**Community Tier:** 🏆 **Tier {tier}** • Based on **{ratings_cnt:,}** community reviews.\n\n"
                f"*Page **{self.page + 1} of {self.max_pages}** • Perks **#{self.page * 4 + 1} to #{self.page * 4 + len(self.current_page_perks)}***"
            ),
            color=color
        )

        for i, p in enumerate(self.current_page_perks):
            p_name = p.get("PerkName", "Unknown")
            p_tier = p.get("Tier", "?")
            p_rate = p.get("Rating", 0)
            p_orig = p.get("PerkKiller") or p.get("Killer") or p.get("Survivor", "General")
            rank_num = self.page * 4 + i + 1
            embed.add_field(
                name=f"#{rank_num} {p_name}",
                value=f"Tier **{p_tier}** • ⭐ **{p_rate}/5**\nTeachable: *{p_orig}*",
                inline=True
            )

        embed.set_image(url=f"attachment://{file.filename}")
        embed.set_footer(text="The Plague • Use buttons to navigate pages or the dropdown below to inspect a perk.")
        return embed, file

    @ui.button(label="Top 4 Meta", style=discord.ButtonStyle.success, emoji="⏮️", row=0)
    async def btn_first(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.page = 0
        self._refresh_components()
        embed, file = await self.get_page_payload()
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="◀️", row=0)
    async def btn_prev(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.page = max(0, self.page - 1)
        self._refresh_components()
        embed, file = await self.get_page_payload()
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="▶️", row=0)
    async def btn_next(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.page = min(self.max_pages - 1, self.page + 1)
        self._refresh_components()
        embed, file = await self.get_page_payload()
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)


class RandomizerSelect(ui.Select):
    """Inspect one of the 4 randomly chosen perks."""
    def __init__(self, perks: List[Dict[str, Any]]):
        options = []
        for i, p in enumerate(perks[:4]):
            p_name = p.get("PerkName", f"Perk {i+1}")
            tier = p.get("Tier", "?")
            rating = p.get("Rating", 0)
            origin = p.get("PerkKiller") or p.get("Killer") or p.get("Survivor", "General")
            options.append(
                discord.SelectOption(
                    label=p_name[:100],
                    description=f"Tier {tier} • Rating: {rating}/5 • From: {origin}"[:100],
                    value=str(i),
                    emoji="🎲"
                )
            )
        super().__init__(
            placeholder="🔍 Inspect a rolled perk...",
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        view: RandomizerView = self.view
        perk = view.current_perks[idx]
        tier = perk.get("Tier", "B")
        embed = discord.Embed(
            title=f"🎲 Rolled Perk: {perk.get('PerkName')}",
            description="Details of the randomly chosen perk.",
            color=TIER_COLORS.get(tier, 0x8A2BE2)
        )
        icon_url = perk.get("PerkIcon") or perk.get("Image")
        if icon_url:
            embed.set_thumbnail(url=icon_url.strip().replace(" ", "%20"))

        rating_val = float(perk.get("Rating", 0))
        origin = perk.get("PerkKiller") or perk.get("Killer") or perk.get("Survivor", "General")
        embed.add_field(name="🏆 Tier", value=f"Tier **{tier}**", inline=True)
        embed.add_field(name="⭐ Rating", value=f"**{rating_val:.2f} / 5.0**", inline=True)
        embed.add_field(name="👤 Teachable From", value=f"**{origin}**", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RandomizerView(ui.View):
    """Interactive Roulette view allowing instant rerolls and role swaps."""
    def __init__(
        self,
        role: str,
        killer_pool: List[Dict[str, Any]],
        perk_pool: List[Dict[str, Any]],
        session,
        locked_killer: Optional[Dict[str, Any]] = None
    ):
        super().__init__(timeout=240)
        self.role = role
        self.killer_pool = killer_pool
        self.perk_pool = perk_pool
        self.session = session
        self.locked_killer = locked_killer
        self.current_killer = locked_killer
        self.current_perks: List[Dict[str, Any]] = []

        self.reroll()

    def reroll(self):
        """Draws 4 unique perks and a killer if applicable."""
        is_killer = "kill" in self.role.lower()
        if is_killer and not self.locked_killer and self.killer_pool:
            self.current_killer = random.choice(self.killer_pool)
        elif not is_killer:
            self.current_killer = None

        if len(self.perk_pool) >= 4:
            self.current_perks = random.sample(self.perk_pool, 4)
        else:
            self.current_perks = list(self.perk_pool)

        # Update select
        for child in list(self.children):
            if isinstance(child, RandomizerSelect):
                self.remove_item(child)
        if self.current_perks:
            self.add_item(RandomizerSelect(self.current_perks))

    async def get_payload(self) -> Tuple[discord.Embed, discord.File]:
        is_killer = "kill" in self.role.lower()
        buf = await generate_randomizer_card(
            self.session,
            self.role,
            self.current_perks,
            killer_info=self.current_killer
        )
        file = discord.File(fp=buf, filename="randomizer.png")

        title = "🎲 DBD Roulette: Killer Randomizer" if is_killer else "🎲 DBD Roulette: Survivor Randomizer"
        color = 0x8A2BE2 if is_killer else 0x5DE2E7

        desc_lines = []
        if is_killer and self.current_killer:
            k_name = self.current_killer.get("KillerName", "Killer")
            k_tier = self.current_killer.get("Tier", "?")
            k_rating = self.current_killer.get("Rating", 0)
            desc_lines.append(f"**Selected Killer:** 🗡️ **{k_name}** (Tier {k_tier} • ⭐ {k_rating}/5)")
        desc_lines.append("*Here is your challenge loadout! Click **Reroll** below to spin again.*")

        embed = discord.Embed(
            title=title,
            description="\n".join(desc_lines),
            color=color
        )

        for i, p in enumerate(self.current_perks):
            p_name = p.get("PerkName", "Unknown")
            tier = p.get("Tier", "?")
            rate = p.get("Rating", 0)
            origin = p.get("PerkKiller") or p.get("Killer") or p.get("Survivor", "General")
            embed.add_field(
                name=f"Perk {i+1}: {p_name}",
                value=f"Tier **{tier}** • ⭐ **{rate}/5**\nTeachable: *{origin}*",
                inline=True
            )

        embed.set_image(url=f"attachment://{file.filename}")
        embed.set_footer(text="The Plague Roulette • Challenge your friends to survive with this build!")
        return embed, file

    @ui.button(label="Reroll Loadout", style=discord.ButtonStyle.primary, emoji="🎲", row=0)
    async def btn_reroll(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        self.reroll()
        embed, file = await self.get_payload()
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)


class TierListView(ui.View):
    """View to switch between Killer Tier list and Survivor Perks Tier list."""
    def __init__(self, killers: List[Dict[str, Any]], surv_perks: List[Dict[str, Any]]):
        super().__init__(timeout=180)
        self.killers = sorted(killers, key=lambda k: float(k.get("Rating", 0)), reverse=True)
        self.surv_perks = sorted(surv_perks, key=lambda p: float(p.get("Rating", 0)), reverse=True)
        self.mode = "killers"

    def get_embed(self) -> discord.Embed:
        if self.mode == "killers":
            embed = discord.Embed(
                title="🏆 Official Killer Tier List (Dennis Reep)",
                description="Community ranking of all 43 Dead by Daylight killers based on player votes.",
                color=0x8A2BE2
            )
            tiers = {"S": [], "A": [], "B": [], "C": [], "D": [], "F": []}
            for k in self.killers:
                t = k.get("Tier", "B")
                tiers.setdefault(t, []).append(k)

            for t_name in ["S", "A", "B", "C", "D"]:
                k_list = tiers.get(t_name, [])
                if k_list:
                    formatted = [f"**{k['KillerName']}** (⭐ {k['Rating']})" for k in k_list]
                    embed.add_field(
                        name=f"Tier {t_name} ({len(k_list)} killers)",
                        value=", ".join(formatted) if len(", ".join(formatted)) < 1024 else ", ".join(formatted[:12]) + "...",
                        inline=False
                    )
            return embed
        else:
            embed = discord.Embed(
                title="🏆 Top 15 Survivor Perks Tier List",
                description="The highest rated survivor perks ranked by the DBD community.",
                color=0x5DE2E7
            )
            for i, p in enumerate(self.surv_perks[:15]):
                embed.add_field(
                    name=f"#{i+1} {p.get('PerkName')}",
                    value=f"Tier **{p.get('Tier')}** • ⭐ **{p.get('Rating')}/5** ({p.get('Survivor')})",
                    inline=True
                )
            return embed

    @ui.button(label="Killer Tier List", style=discord.ButtonStyle.primary, emoji="🗡️")
    async def btn_killers(self, interaction: discord.Interaction, button: ui.Button):
        self.mode = "killers"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="Top Survivor Perks", style=discord.ButtonStyle.secondary, emoji="🏃")
    async def btn_survivors(self, interaction: discord.Interaction, button: ui.Button):
        self.mode = "survivors"
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
