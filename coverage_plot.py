import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt

root = ET.parse("coverage.xml").getroot()

modules = []
coverage = []

for cls in root.findall(".//class"):
    filename = cls.get("filename").replace("src/auction_house/", "")
    lines = cls.findall("./lines/line")

    if not lines:
        continue

    total = len(lines)
    covered = sum(int(line.get("hits")) > 0 for line in lines)

    modules.append(filename)
    coverage.append(covered / total * 100)

fig, ax = plt.subplots(figsize=(10, 7))

ax.barh(modules, coverage)
ax.set_xlim(0, 100)
ax.set_xlabel("Coverage (%)")
ax.set_title("Auction House – Test Coverage")
ax.axvline(88, color="red", linestyle="--", label="Overall coverage (88%)")
ax.legend()
ax.grid(axis="x", alpha=0.3)
ax.invert_yaxis()

plt.tight_layout()
plt.savefig("coverage.png", dpi=300, bbox_inches="tight")
plt.show()