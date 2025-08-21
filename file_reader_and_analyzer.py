import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go


# df = pd.read_csv(r"C:\Users\dvecseri\WWT International\Tractor Performance Project - General\AE25027\ToolLog_UZ688_250213_034846.csv")
df = pd.read_csv(r"C:\Users\dvecseri\WWT International\Tractor Performance Project - General\AE24277\FullDatasets\WSTableEdited_ZK401_SSL_241108_213346.csv")


start = 5700000
# end = 8000000
end = 5900000
# time_section = df.loc[(df["ElapsedTime"] > start) & (df["ElapsedTime"] < end)]
# data_section = df.loc[(df["Pressure"] > start) & (df["Pressure"] < end)]
#---------------------------
# df.plot(x = "Time", y = "Pressure", kind = "line")

# plt.show()

#---------------------------
# fig = px.line(df, x = "Time", y = "Pressure", title = "Bore Pressure vs Time", labels = {"Time": "Time (s)", "Pressure": "Bore Pressure (psi)"})
# fig = px.line(x = time_section, y = data_section, title = "Bore Pressure vs Time", labels = {"Time": "Time (s)", "Pressure": "Bore Pressure (psi)"})
print(df.head())
# fig = px.line(df, x = "DateTime", y = "Pressure", title = "Bore Pressure vs Time", labels = {"Time": "Time (s)", "Pressure": "Bore Pressure (psi)"})

# fig.show()

#---------------------------
ds = df.iloc[start:end]
ds.to_csv('tractor_section.csv', index=False, encoding='utf-8')

# fig = go.Figure(data=[go.Scattergl(x = df["DateTime"].iloc[start:end], y = df["Pressure"].iloc[start:end], mode = "lines", name="Bore Pressure")],)
fig = go.Figure(data=[go.Scattergl(y = df["Pressure"].iloc[start:end], mode = "lines", name="Bore Pressure")],)

fig.show()


# print(df["Time"].head())
# print(time_section.head())
# print(data_section.head())



# import pandas as pd
# import numpy as np
# import plotly.express as px
# import matplotlib.pyplot as plt

# def get_window_by_seconds(df, start_str, end_str,
#                           time_col='DateTime',
#                           pressure_col='Pressure',
#                           time_fmt='%d-%b-%Y %H:%M:%S.%f'):
#     # ----------------------
#     # Select rows whose timestamps (rounded/floored to whole seconds) fall between
#     # start_str and end_str. The original millisecond-resolution timestamps are preserved.
    
#     # Inputs:
#     #   df         - original DataFrame (must contain time_col and pressure_col)
#     #   start_str  - e.g. '13-Feb-2025 06:46:13'  (no milliseconds required)
#     #   end_str    - e.g. '13-Feb-2025 06:50:00'
#     #   time_col   - name of the column containing time strings (default 'Time')
#     #   pressure_col - name of pressure column
#     #   time_fmt   - format used to parse the original time strings (default matches your example)
    
#     # Returns:
#     #   df_section - DataFrame copy of rows in the selected second-window (original timestamps kept)
#     #   times_ms   - numpy array of datetime64[ns] with milliseconds (original times)
#     #   pressures  - numpy array of pressures (float)
#     # ----------------------
#     # parse times to datetimes (non-destructive: create new column)
#     df = df.copy()
#     df['_Time_dt'] = pd.to_datetime(df[time_col], format=time_fmt, errors='coerce')
#     # sanity: ensure pressure numeric
#     df[pressure_col] = pd.to_numeric(df[pressure_col], errors='coerce')
#     # drop bad rows
#     df = df.dropna(subset=['_Time_dt', pressure_col]).reset_index(drop=True)
    
#     # floored seconds column used only for masking (preserves original dt with ms)
#     df['_Time_secs'] = df['_Time_dt'].dt.floor('S')
    
#     # parse provided start/end (they may be day-month or ISO; let pandas infer)
#     start_dt = pd.to_datetime(start_str, errors='coerce')
#     end_dt   = pd.to_datetime(end_str, errors='coerce')
#     if pd.isna(start_dt) or pd.isna(end_dt):
#         raise ValueError("start_str or end_str could not be parsed. Use e.g. '13-Feb-2025 06:46:13'")
    
#     # mask using floored second-resolution times (inclusive)
#     mask = (df['_Time_secs'] >= start_dt) & (df['_Time_secs'] <= end_dt)
#     df_section = df.loc[mask].copy()
    
#     # results: original timestamps with ms and pressures
#     times_ms = df_section['_Time_dt'].to_numpy()
#     pressures = df_section[pressure_col].to_numpy()
    
#     # drop helper columns from returned df to keep it clean
#     df_section = df_section.drop(columns=['_Time_secs'])
    
#     return df_section, times_ms, pressures

# # ----------------------
# # Example usage:
# # ----------------------
# # fp = r"C:\Users\dvecseri\WWT International\Tractor Performance Project - General\AE25027\ToolLog_UZ688_250213_034846.csv"
# # fp = r"C:\Users\dvecseri\WWT International\Tractor Performance Project - General\AE25107\WSTable_UZ701_SSL_250512_084215.csv"
# fp = r"C:\Users\dvecseri\WWT International\Tractor Performance Project - General\AE24277\FullDatasets\WSTableEdited_ZK401_SSL_241108_213346.csv"
# df = pd.read_csv(fp)

# # start = '13-Feb-2025 13:15:00'
# # end   = '13-Feb-2025 14:00:00'
# # start = '2025-Nov-08 21:33:46'
# # end   = '2025-Nov-09 00:28:32'
# start = '08-Nov-2025 21:33:46'
# end   = '09-Nov-2025 00:28:32'

# # df_sel, times_ms, pressures = get_window_by_seconds(df, start, end,)
# df_sel, times_ms, pressures = get_window_by_seconds(df, start, end, time_col= 'DateTime', pressure_col='Pressure', time_fmt = '%Y-%b-%d %H:%M:%S.%f')

# print(f"Rows selected: {len(df_sel)}")
# print(df_sel[['DateTime','Pressure']].head())   # original Time strings (with ms) are preserved

# # optional: interactive Plotly plot using the millisecond-resolution datetimes
# fig = px.line(df_sel, x=pd.to_datetime(df_sel['DateTime'], format='%d-%b-%Y %H:%M:%S.%f'),
#               y='Pressure', title=f'Pressure between {start} and {end}',
#               labels={'x':'DateTime','Pressure':'Bore Pressure (psi)'})
# fig.show()

# # # optional: Matplotlib plot (shows ms precision on x-axis ticks)
# # plt.figure(figsize=(10,4))
# # plt.plot(pd.to_datetime(df_sel['Time'], format='%d-%b-%Y %H:%M:%S.%f'),
# #          df_sel['Pressure'], marker='.', linestyle='-')
# # plt.xticks(rotation=30)
# # plt.tight_layout()
# # plt.show()
