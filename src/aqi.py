"""AQI calculation from raw PM2.5 / PM10 concentrations."""

BREAKPOINTS_PM25 = [
    (0.0, 12.0, 0, 50),
    (12.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 500.4, 301, 500),
]

BREAKPOINTS_PM10 = [
    (0, 54, 0, 50),
    (55, 154, 51, 100),
    (155, 254, 101, 150),
    (255, 354, 151, 200),
    (355, 424, 201, 300),
    (425, 604, 301, 500),
]

CATEGORIES = [
    (0, 50, "good", "Good"),
    (51, 100, "moderate", "Moderate"),
    (101, 150, "unhealthy_sensitive", "Unhealthy for Sensitive Groups"),
    (151, 200, "unhealthy", "Unhealthy"),
    (201, 300, "very_unhealthy", "Very Unhealthy"),
    (301, 500, "hazardous", "Hazardous"),
]


def _conc_to_aqi(conc, breakpoints):
    if conc is None:
        return None
    for cl, ch, al, ah in breakpoints:
        if cl <= conc <= ch:
            return round(((ah - al) / (ch - cl)) * (conc - cl) + al)
    if conc > breakpoints[-1][1]:
        return breakpoints[-1][3]
    return None


def pm25_to_aqi(pm25):
    return _conc_to_aqi(pm25, BREAKPOINTS_PM25)


def pm10_to_aqi(pm10):
    return _conc_to_aqi(pm10, BREAKPOINTS_PM10)


def aqi_info(aqi):
    if aqi is None:
        return {"key": "unknown", "label": "Unknown", "color": "#cccccc"}
    for al, ah, key, label in CATEGORIES:
        if al <= aqi <= ah:
            colors = {
                "good": "#00E400",
                "moderate": "#FFFF00",
                "unhealthy_sensitive": "#FF7E00",
                "unhealthy": "#FF0000",
                "very_unhealthy": "#8F3F97",
                "hazardous": "#7E0023",
                "unknown": "#cccccc",
            }
            text_colors = {
                "good": "#000000",
                "moderate": "#000000",
                "unhealthy_sensitive": "#000000",
                "unhealthy": "#FFFFFF",
                "very_unhealthy": "#FFFFFF",
                "hazardous": "#FFFFFF",
                "unknown": "#000000",
            }
            return {
                "key": key,
                "label": label,
                "color": colors.get(key, "#ccc"),
                "text_color": text_colors.get(key, "#000"),
            }
    return {"key": "hazardous", "label": "Hazardous", "color": "#7E0023", "text_color": "#FFFFFF"}
