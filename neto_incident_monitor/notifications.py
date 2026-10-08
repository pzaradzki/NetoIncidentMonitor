"""Format one notification for the unique incidents found in a cycle."""
def batch_text(incidents):
    unique = {incident["number"]: incident for incident in incidents}
    if not unique:
        return None
    numbers = sorted(unique)
    if len(numbers) == 1:
        incident = unique[numbers[0]]
        return f"Nowy incydent: {numbers[0]}", (incident.get("short_description") or incident.get("summary") or "Szczegóły w historii zgłoszeń.")[:240]
    message = ", ".join(numbers[:6])
    if len(numbers) > 6:
        message += f" oraz {len(numbers) - 6} kolejnych."
    message += "\nSzczegóły w historii zgłoszeń."
    return f"Nowe incydenty: {len(numbers)}", message
