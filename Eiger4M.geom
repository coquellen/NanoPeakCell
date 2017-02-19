clen = 0.108
photon_energy = 12812.3

adu_per_photon = 1
res = 13333.3   ; 75 micron pixel size

; Uncomment these lines for multi-event file
dim0 = %
dim1 = ss
dim2 = fs
; data = /entry/data/data

; Uncomment this line for single-event test file
data = /data

; Mask out strips between panels
bad_v0/min_fs = 1030
bad_v0/min_ss = 0
bad_v0/max_fs = 1039
bad_v0/max_ss = 2166

bad_h0/min_fs = 0
bad_h0/min_ss = 514
bad_h0/max_fs = 2069
bad_h0/max_ss = 550

bad_h1/min_fs = 0
bad_h1/min_ss = 1065
bad_h1/max_fs = 2069
bad_h1/max_ss = 1101

bad_h2/min_fs = 0
bad_h2/min_ss = 1616
bad_h2/max_fs = 2069
bad_h2/max_ss = 1652

; Mask out bad pixels
;mask_file = eiger-badmap.h5
;mask = /data/data
;mask_good = 0x0
;mask_bad = 0x1

panel0/min_fs = 0
panel0/min_ss = 0
panel0/max_fs = 2069
panel0/max_ss = 2166
panel0/corner_x = -1020.0
panel0/corner_y = -1084.0
panel0/fs = x
panel0/ss = y
