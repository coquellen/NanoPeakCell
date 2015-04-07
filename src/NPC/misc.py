def parseBoolString(s):
    return s.strip().lower in ('true', 't', 'yes', '1')

print parseBoolString('False')
print bool(False)
