import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import make_interp_spline
import streamlit as st

st.set_page_config(
    page_title="TernPlot | Ternary Envelope Diagram",
    page_icon="🔺",
    layout="wide",
)

st.title("🔺 TernPlot — Ternary Diagram & Envelope Generator")
st.caption("Define your mixture and components, choose your fraction basis, plot points with an envelope, and download as PNG.")

# --- SIDEBAR: USER-DEFINED SYSTEM & BASIS ---
st.sidebar.header("1. Mixture & Components")
mixture_type = st.sidebar.text_input(
    "Mixture / System Type",
    value="",
    placeholder="e.g., Ternary Liquid Mixture, Phase Study",
)
comp_a = st.sidebar.text_input("Component A (Top Vertex)", value="Component A")
comp_b = st.sidebar.text_input("Component B (Bottom-Left Vertex)", value="Component B")
comp_c = st.sidebar.text_input("Component C (Bottom-Right Vertex)", value="Component C")

st.sidebar.header("2. Fraction Basis & Input Mode")
fraction_basis = st.sidebar.selectbox(
    "Select Fraction Type",
    ["Volume Fraction", "Mole Fraction", "Mass Fraction"],
)
input_style = st.sidebar.radio(
    "How are you entering values?",
    ["Raw Amounts (auto-normalize to fraction)", "Direct Fractions (0 to 1)"],
)

st.sidebar.header("3. Envelope & Chart Options")
show_envelope = st.sidebar.checkbox("Connect Points with Envelope", value=True)
smooth_curve = st.sidebar.checkbox("Smooth Spline Envelope", value=True)
line_style_label = st.sidebar.selectbox("Envelope Line Style", ["Solid", "Dashed", "Dash-Dot"])
line_style_map = {"Solid": "-", "Dashed": "--", "Dash-Dot": "-."}
show_grid = st.sidebar.checkbox("Show 10% Gridlines", value=True)
show_point_labels = st.sidebar.checkbox("Show Point Labels", value=True)
point_color = st.sidebar.color_picker("Point Color", "#B45309")
envelope_color = st.sidebar.color_picker("Envelope Color", "#1E3A5F")

# Clean display names if user leaves a component blank
name_a = comp_a.strip() if comp_a.strip() else "Component A"
name_b = comp_b.strip() if comp_b.strip() else "Component B"
name_c = comp_c.strip() if comp_c.strip() else "Component C"
system_title = mixture_type.strip() if mixture_type.strip() else "Ternary System"

basis_short = {
    "Volume Fraction": "Vol. Frac.",
    "Mole Fraction": "Mole Frac.",
    "Mass Fraction": "Mass Frac.",
}[fraction_basis]

# --- INITIAL DATA TABLE ---
if "ternary_table" not in st.session_state:
  st.session_state.ternary_table = pd.DataFrame({
      "Point": ["P1", "P2", "P3", "P4"],
      "A": [0.40, 0.30, 0.20, 0.10],
      "B": [0.30, 0.40, 0.50, 0.60],
      "C": [0.30, 0.30, 0.30, 0.30],
  })

st.subheader(f"Data Input — {system_title} ({fraction_basis})")
if "Raw Amounts" in input_style:
  st.write(
      f"Enter measured quantities (e.g., mL, mol, or g) for **{name_a}**, **{name_b}**, and"
      f" **{name_c}**. Each row is divided by its row total to get **{fraction_basis}**."
  )
else:
  st.write(
      f"Enter **{fraction_basis}** values for **{name_a}**, **{name_b}**, and **{name_c}**."
      " Rows will be normalized so the three fractions sum to 1.00."
  )

edited_df = st.data_editor(
    st.session_state.ternary_table,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Point": st.column_config.TextColumn("Point ID"),
        "A": st.column_config.NumberColumn(f"{name_a} ({basis_short})", min_value=0.0, step=0.01, format="%.4f"),
        "B": st.column_config.NumberColumn(f"{name_b} ({basis_short})", min_value=0.0, step=0.01, format="%.4f"),
        "C": st.column_config.NumberColumn(f"{name_c} ({basis_short})", min_value=0.0, step=0.01, format="%.4f"),
    },
)

df_work = edited_df.copy()
for col in ["A", "B", "C"]:
  df_work[col] = pd.to_numeric(df_work[col], errors="coerce").fillna(0.0)

df_work["Row_Sum"] = df_work["A"] + df_work["B"] + df_work["C"]
df_valid = df_work[df_work["Row_Sum"] > 0].copy()

if not df_valid.empty:
  df_valid["xA"] = df_valid["A"] / df_valid["Row_Sum"]
  df_valid["xB"] = df_valid["B"] / df_valid["Row_Sum"]
  df_valid["xC"] = df_valid["C"] / df_valid["Row_Sum"]

# --- TERNARY COORDINATE CONVERSION ---
# Top vertex = A (1, 0, 0) -> (0.5, sqrt(3)/2)
# Bottom-left vertex = B (0, 1, 0) -> (0.0, 0.0)
# Bottom-right vertex = C (0, 0, 1) -> (1.0, 0.0)
TRI_H = np.sqrt(3.0) / 2.0


def ternary_to_xy(xa, xb, xc):
  x = xc + 0.5 * xa
  y = TRI_H * xa
  return x, y


fig, ax = plt.subplots(figsize=(7.6, 6.8), dpi=300)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# Triangle boundary
ax.plot([0.0, 1.0, 0.5, 0.0], [0.0, 0.0, TRI_H, 0.0], color="#111827", linewidth=2.0, zorder=2)

# Gridlines
if show_grid:
  ticks = np.linspace(0.1, 0.9, 9)
  for t in ticks:
    # Constant A (horizontal)
    p1x, p1y = ternary_to_xy(t, 1.0 - t, 0.0)
    p2x, p2y = ternary_to_xy(t, 0.0, 1.0 - t)
    ax.plot([p1x, p2x], [p1y, p2y], color="#D1D5DB", linestyle=":", linewidth=0.8, zorder=1)

    # Constant B
    p3x, p3y = ternary_to_xy(1.0 - t, t, 0.0)
    p4x, p4y = ternary_to_xy(0.0, t, 1.0 - t)
    ax.plot([p3x, p4x], [p3y, p4y], color="#D1D5DB", linestyle=":", linewidth=0.8, zorder=1)

    # Constant C
    p5x, p5y = ternary_to_xy(1.0 - t, 0.0, t)
    p6x, p6y = ternary_to_xy(0.0, 1.0 - t, t)
    ax.plot([p5x, p6x], [p5y, p6y], color="#D1D5DB", linestyle=":", linewidth=0.8, zorder=1)

# Vertex labels
ax.text(0.5, TRI_H + 0.04, name_a, ha="center", va="bottom", fontsize=11, fontweight="bold", color="#111827")
ax.text(-0.03, -0.04, name_b, ha="right", va="top", fontsize=11, fontweight="bold", color="#111827")
ax.text(1.03, -0.04, name_c, ha="left", va="top", fontsize=11, fontweight="bold", color="#111827")

# Axis direction labels
ax.text(0.20, TRI_H * 0.52, f"{name_a} {basis_short}", ha="right", va="center", rotation=60, fontsize=9, color="#4B5563")
ax.text(0.80, TRI_H * 0.52, f"{name_c} {basis_short}", ha="left", va="center", rotation=-60, fontsize=9, color="#4B5563")
ax.text(0.50, -0.075, f"{name_b} {basis_short}", ha="center", va="top", fontsize=9, color="#4B5563")

# Plot data points and connecting envelope
if not df_valid.empty:
  px, py = ternary_to_xy(df_valid["xA"].values, df_valid["xB"].values, df_valid["xC"].values)

  if show_envelope and len(px) >= 2:
    ls = line_style_map[line_style_label]
    if smooth_curve and len(px) >= 4:
      u = np.linspace(0.0, 1.0, len(px))
      u_dense = np.linspace(0.0, 1.0, 200)
      deg = min(3, len(px) - 1)
      sx = make_interp_spline(u, px, k=deg)(u_dense)
      sy = make_interp_spline(u, py, k=deg)(u_dense)
      ax.plot(sx, sy, color=envelope_color, linestyle=ls, linewidth=2.2, label="Envelope", zorder=3)
    else:
      ax.plot(px, py, color=envelope_color, linestyle=ls, linewidth=2.2, label="Envelope", zorder=3)

  ax.scatter(px, py, color=point_color, edgecolor="white", linewidth=1.2, s=75, label="Data Points", zorder=4)

  if show_point_labels:
    for i, (_, row) in enumerate(df_valid.iterrows()):
      lbl = str(row["Point"]).strip() if str(row["Point"]).strip() else f"P{i+1}"
      ax.annotate(lbl, (px[i], py[i]), xytext=(6, 6), textcoords="offset points", fontsize=9, fontweight="bold", color="#111827", zorder=5)

  ax.legend(loc="upper right", frameon=True, facecolor="#F9FAFB", edgecolor="#D1D5DB")

ax.set_title(f"{system_title} ({fraction_basis})", fontsize=13, fontweight="bold", pad=28, color="#111827")
ax.set_xlim(-0.15, 1.15)
ax.set_ylim(-0.14, TRI_H + 0.12)
ax.set_aspect("equal")
ax.axis("off")
plt.tight_layout()

buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
buf.seek(0)

st.subheader("Ternary Diagram")
col_chart, col_fractions = st.columns([1.4, 1.0])

with col_chart:
  st.pyplot(fig, use_container_width=True)
  safe_name = system_title.lower().replace(" ", "_")
  st.download_button(
      label="Download Diagram (PNG)",
      data=buf,
      file_name=f"{safe_name}_ternary_diagram.png",
      mime="image/png",
      type="primary",
  )

with col_fractions:
  st.markdown(f"**Normalized {fraction_basis}**")
  if not df_valid.empty:
    out_df = pd.DataFrame({
        "Point": df_valid["Point"].astype(str),
        f"{name_a} ({basis_short})": df_valid["xA"].round(4),
        f"{name_b} ({basis_short})": df_valid["xB"].round(4),
        f"{name_c} ({basis_short})": df_valid["xC"].round(4),
    })
    st.dataframe(out_df, use_container_width=True, hide_index=True)
  else:
    st.info("Enter positive values in at least one row to compute fractions and plot.")
