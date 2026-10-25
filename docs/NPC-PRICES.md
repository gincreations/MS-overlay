# NPC purchase-price references

Checked 2026-10-20 against [MapleClassic Wiki](https://mapleclassic.wiki/wiki/Shops), a community guide for **MapleStory Classic World**, not modern GMS or a private-server shop list.

These are **NPC purchase prices**, not the amount an NPC pays when you sell an item. The app bundles this snapshot; it does not fetch prices, visit the wiki, or upload data at runtime.

## Confidence and selection policy

- The item pages and most shop pages label their data **pre-launch**; Mr. Sweatbottom's shop page labels it **0.9.0**. These are documented community references, not independently verified current in-game quotes or official Nexon prices.
- Cross-checked the item “Sold by” tables with [Arturo](https://mapleclassic.wiki/wiki/Arturo), [Dr. Faymus](https://mapleclassic.wiki/wiki/Dr._Faymus), [Raymond](https://mapleclassic.wiki/wiki/Raymond), [24 Hr Mobile Store](https://mapleclassic.wiki/wiki/24_Hr_Mobile_Store), and [Mr. Sweatbottom](https://mapleclassic.wiki/wiki/Mr._Sweatbottom). The Orange Potion page has inconsistent descriptive HP/sell-price prose; the matching item/shop **purchase tables**, not that prose, support 150.
- Prefer a standard, unrestricted listed shop price where available. Apple uses Arturo's 20, not the sauna's 30; Unagi uses Ant Tunnel Park's 1,000, not the sauna's 1,800. No assumption that the user bought from that shop.
- Three defaults are gated: Elixir, Orange Juice, Grape Juice. The panel shows the relevant rank/stock condition. Elixir's finite stock is **not** treated as an indefinitely available refill source.
- A missing recorded seller means **unknown purchase price**, not proof that no NPC can ever sell the item. Six such items stay manual. No sell-price multiplier, old GMS price, or fabricated player-market average is substituted.
- Custom prices (including 0) override references and survive upgrades/restarts. Enter your actual paid price or your own average unit cost. No online market average is claimed. If averaging purchases, divide total mesos paid by total units bought, then round to whole mesos.
- Blank + Save hides costs for that item; **Use NPC** restores the reference. Items with no prior saved price gain a reference automatically if one exists.
- Price changes revalue the whole current session estimate, not a historical purchase ledger. They do not reset counting or EXP/meso tracking.

## Bundled references

| Item | Mesos / item | Reference shop / restriction | Item source revision |
|---|---:|---|---|
| Red Potion | 50 | Arturo (Perion); standard shop price. | [Source](https://mapleclassic.wiki/index.php?title=Red_Potion&oldid=86254) |
| Orange Potion | 150 | Arturo (Perion); standard shop price. | [Source](https://mapleclassic.wiki/index.php?title=Orange_Potion&oldid=86014) |
| White Potion | 350 | Arturo (Perion); standard shop price. | [Source](https://mapleclassic.wiki/index.php?title=White_Potion&oldid=87223) |
| Blue Potion | 220 | Arturo (Perion); standard shop price. | [Source](https://mapleclassic.wiki/index.php?title=Blue_Potion&oldid=87190) |
| Elixir | 3000 | Raymond / Max: Citizen of Honor; 100 per user, no refill. | [Source](https://mapleclassic.wiki/index.php?title=Elixir&oldid=88386) |
| Power Elixir | Manual | No NPC seller recorded; enter paid or average unit price. | [Source](https://mapleclassic.wiki/index.php?title=Power_Elixir&oldid=86105) |
| Mana Elixir | Manual | No NPC seller recorded; enter paid or average unit price. | [Source](https://mapleclassic.wiki/index.php?title=Mana_Elixir&oldid=84832) |
| Watermelon | Manual | No NPC seller recorded; enter paid or average unit price. | [Source](https://mapleclassic.wiki/index.php?title=Watermelon&oldid=86606) |
| Ice Cream Pop | Manual | No NPC seller recorded; enter paid or average unit price. | [Source](https://mapleclassic.wiki/index.php?title=Ice_Cream_Pop&oldid=85788) |
| Apple | 20 | Arturo (Perion): 20; sauna shop: 30. | [Source](https://mapleclassic.wiki/index.php?title=Apple&oldid=84861) |
| Egg | 30 | Arturo (Perion); standard shop price. | [Source](https://mapleclassic.wiki/index.php?title=Egg&oldid=85531) |
| Orange | 50 | Arturo (Perion); standard shop price. | [Source](https://mapleclassic.wiki/index.php?title=Orange&oldid=86003) |
| Lemon | 150 | Arturo (Perion); standard shop price. | [Source](https://mapleclassic.wiki/index.php?title=Lemon&oldid=87205) |
| Hamburger | 350 | 24 Hr Mobile Store (Ant Tunnel Park). | [Source](https://mapleclassic.wiki/index.php?title=Hamburger&oldid=85754) |
| Hot Dog | 180 | 24 Hr Mobile Store (Ant Tunnel Park). | [Source](https://mapleclassic.wiki/index.php?title=Hot_Dog&oldid=85784) |
| Orange Juice | 540 | Raymond / Max: Trusted Neighbor or higher. | [Source](https://mapleclassic.wiki/index.php?title=Orange_Juice&oldid=86009) |
| Grape Juice | 1260 | Raymond / Max: Guardian of the Village or higher. | [Source](https://mapleclassic.wiki/index.php?title=Grape_Juice&oldid=85650) |
| Reindeer Milk | Manual | No NPC seller recorded; enter paid or average unit price. | [Source](https://mapleclassic.wiki/index.php?title=Reindeer_Milk&oldid=86307) |
| Sunrise Dew | Manual | No NPC seller recorded; enter paid or average unit price. | [Source](https://mapleclassic.wiki/index.php?title=Sunrise_Dew&oldid=86499) |
| Pure Water | 1120 | 24 Hr Mobile Store / Mr. Sweatbottom. | [Source](https://mapleclassic.wiki/index.php?title=Pure_Water&oldid=86111) |
| Unagi | 1000 | Ant Tunnel Park: 1,000; sauna shop: 1,800. | [Source](https://mapleclassic.wiki/index.php?title=Unagi&oldid=86588) |

## Attribution

Price facts were checked against MapleClassic Wiki contributors' item/shop tables. The site states [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); this sourced reference table and the NPC-price metadata are attributed accordingly, not relicensed as MIT. Notes are condensed and prices selected as described above. Other app code retains its existing license. Item artwork has separate [Nexon attribution](CONSUMABLE-ARTWORK.md).
