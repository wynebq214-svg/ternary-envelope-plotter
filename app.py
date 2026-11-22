import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import make_interp_spline
import io

st.set_page_config(
    page_title="Ternary Envelope Plotter",
    page_icon="🔺",
    layout="wide"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #FBF9F6;
        color: #1F2937;
    }
    .header-box {
        background: linear-gradient(135deg, #1E3A5F 0%, #2B6CB0 100%);
        color: #FFFFFF;
        padding: 1.5rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header-box">
        <h1 style="margin:0;">🔺 TernPlot</h1>
        <p style="margin:4px 0 0 0; opacity:0.9;">Plot volume or mass measurements onto a ternary triangle, draw a connecting envelope, and export as PNG.</p>
    </div>
""", unsafe_allow_html=True)

# --- SIDEBAR: FLUID / MIXTURE & COMPONENTS ---
st.sidebar.header("1. Mixture & Components")
mixture_label = st.sidebar.text_input("Fluid / Mixture Name", value="Water - Ethanol - Ethyl Acetate")
basis_mode = st.sidebar.selectbox("Input Basis", ["Volume (mL)", "Mass (g)"])

comp_a = st.sidebar.text_input("Top Vertex (Component A)", value="Component A (Solvent)")
comp_b = st.sidebar.text_input("Bottom-Left Vertex (Component B)", value="Component B (Diluent)")
comp_c = st.sidebar.text_input("Bottom-Right Vertex (Component C)", value="Component C (Solute)")

st.sidebar.header("2. Envelope & Plot Style")
show_envelope = st.sidebar.checkbox("Draw Connecting Envelope", value=True)
smooth_envelope = st.sidebar.checkbox("Smooth Spline Curve", value=True)
envelope_style = st.sidebar.selectbox("Envelope Line Style", ["Solid (-)", "Dashed (--)", "Dash-Dot (-.)"])
style_map = {"Solid (-)": "-", "Dashed (--)": "--", "Dash-Dot (-.)": "-."}

point_color = st.sidebar.color_picker("Point Color", "#C2410C")
line_color = st.sidebar.color_picker("Envelope Color", "#1E3A5F")
show_grid = st.sidebar.checkbox("Show Ternary Gridlines", value=True)
show_labels = st.sidebar.checkbox("Label Point Numbers (P1, P2...)", value=True)

# --- HELPER: TERNARY TO CARTESIAN (EQUILATERAL TRIANGLE) ---
# Vertex A = (0.5, sqrt(3)/2) -> top (100% A)
# Vertex B = (0.0, 0.0)         -> bottom-left (100% B)
# Vertex C = (1.0, 0.0)         -> bottom-right (100% C)
# Given fractions (fA, fB, fC) summing to 1:
# x = fC + 0.5 * fA
# y = (sqrt(3)/2) * fA
H = np.sqrt(3.0) / 2.0

def to_xy(fA, fB, fC):
    x = fC + 0.5 * fA
    y = H * fA
    return x, y

# --- MAIN AREA: DATA ENTRY ---
if "data_df" not in st.session_state:
    st.session_state.data_df = pd.DataFrame({
        "Label": ["P1", "P2", "P3", "P4", "P5"],
        "Val_A": [5.0, 4.0, 3.0, 2.0, 1.0],
        "Val_B": [3.0, 3.5, 4.0, 4.5, 5.0],
        "Val_C": [2.0, 2.5, 3.0, 3.5, 4.0],
    })

unit_short = "mL" if "Volume" in basis_mode else "g"

st.subheader(f"Enter Measurements ({basis_mode})")
st.caption("Edit the table below or add/remove rows. Each row is automatically normalized so A + B + C = 100% of that sample.")

edited_df = st.data_editor(
    st.session_state.data_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Label": st.column_config.TextColumn("Point ID"),
        "Val_A": st.column_config.NumberColumn(f"{comp_a} ({unit_short})", min_value=0.0, step=0.1, format="%.2f"),
        "Val_B": st.column_config.NumberColumn(f"{comp_b} ({unit_short})", min_value=0.0, step=0.1, format="%.2f"),
        "Val_C": st.column_config.NumberColumn(f"{comp_c} ({unit_short})", min_value=0.0, step=0.1, format="%.2f"),
    }
)

# Compute normalized fractions
df_calc = edited_df.copy()
df_calc["Val_A"] = pd.to_numeric(df_calc["Val_A"], errors="coerce").fillna(0.0)
df_calc["Val_B"] = pd.to_numeric(df_calc["Val_B"], errors="coerce").fillna(0.0)
df_calc["Val_C"] = pd.to_numeric(df_calc["Val_C"], errors="coerce").fillna(0.0)
df_calc["Total"] = df_calc["Val_A"] + df_calc["Val_B"] + df_calc["Val_C"]

valid_mask = df_calc["Total"] > 0
df_valid = df_calc[valid_mask].copy()

if len(df_valid) > 0:
    df_valid["Frac_A"] = df_valid["Val_A"] / df_valid["Total"]
    df_valid["Frac_B"] = df_valid["Val_B"] / df_valid["Total"]
    df_valid["Frac_C"] = df_valid["Val_C"] / df_valid["Total"]
    df_valid["Pct_A"] = (df_valid["Frac_A"] * 100).round(2)
    df_valid["Pct_B"] = (df_valid["Frac_B"] * 100).round(2)
    df_valid["Pct_C"] = (df_valid["Frac_C"] * 100).round(2)

# --- DRAW TERNARY DIAGRAM ---
fig, ax = plt.subplots(figsize=(7.5, 6.8), dpi=300)
fig.patch.set_facecolor("#FFFFFF")
ax.set_facecolor("#FFFFFF")

# Outer triangle border
vx = [0.0, 1.0, 0.5, 0.0]
vy = [0.0, 0.0, H, 0.0]
ax.plot(vx, vy, color="#111827", linewidth=2.0, zorder=2)

# Gridlines every 10% (0.1)
if show_grid:
    steps = np.linspace(0.1, 0.9, 9)
    for s in steps:
        # Constant fA = s (horizontal line)
        x1, y1 = to_xy(s, 1.0 - s, 0.0)
        x2, y2 = to_xy(s, 0.0, 1.0 - s)
        ax.plot([x1, x2], [y1, y2], color="#D1D5DB", linestyle=":", linewidth=0.8, zorder=1)

        # Constant fB = s (parallel to right edge A-C)
        x3, y3 = to_xy(1.0 - s, s, 0.0)
        x4, y4 = to_xy(0.0, s, 1.0 - s)
        ax.plot([x3, x4], [y3, y4], color="#D1D5DB", linestyle=":", linewidth=0.8, zorder=1)

        # Constant fC = s (parallel to left edge A-B)
        x5, y5 = to_xy(1.0 - s, 0.0, s)
        x6, y6 = to_xy(0.0, 1.0 - s, s)
        ax.plot([x5, x6], [y5, y6], color="#D1D5DB", linestyle=":", linewidth=0.8, zorder=1)

# Vertex labels
ax.text(0.5, H + 0.04, comp_a, ha="center", va="bottom", fontsize=11, fontweight="bold", color="#111827")
ax.text(-0.03, -0.04, comp_b, ha="right", va="top", fontsize=11, fontweight="bold", color="#111827")
ax.text(1.03, -0.04, comp_c, ha="left", va="top", fontsize=11, fontweight="bold", color="#111827")

# Side axis titles
ax.text(0.21, H * 0.52, f"← {comp_a} %", ha="right", va="center", rotation=60, fontsize=9, color="#4B5563")
ax.text(0.79, H * 0.52, f"{comp_c} % →", ha="left", va="center", rotation=-60, fontsize=9, color="#4B5563")
ax.text(0.5, -0.075, f"← {comp_b} %", ha="center", va="top", fontsize=9, color="#4B5563")

# Plot points & envelope
if len(df_valid) > 0:
    xs, ys = to_xy(df_valid["Frac_A"].values, df_valid["Frac_B"].values, df_valid["Frac_C"].values)

    if show_envelope and len(xs) >= 2:
        ls = style_map[envelope_style]
        if smooth_envelope and len(xs) >= 4:
            t_param = np.linspace(0, 1, len(xs))
            t_fine = np.linspace(0, 1, 200)
            k_deg = min(3, len(xs) - 1)
            spl_x = make_interp_spline(t_param, xs, k=k_deg)
            spl_y = make_interp_spline(t_param, ys, k=k_deg)
            ax.plot(spl_x(t_fine), spl_y(t_fine), color=line_color, linestyle=ls, linewidth=2.2, label="Envelope", zorder=3)
        else:
            ax.plot(xs, ys, color=line_color, linestyle=ls, linewidth=2.2, label="Envelope", zorder=3)

    ax.scatter(xs, ys, color=point_color, edgecolor="#FFFFFF", linewidth=1.2, s=75, label="Measured Points", zorder=4)

    if show_labels:
        for idx, (_, row) in enumerate(df_valid.iterrows()):
            lbl = str(row["Label"]) if str(row["Label"]).strip() else f"P{idx+1}"
            ax.annotate(
                lbl,
                (xs[idx], ys[idx]),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=9,
                fontweight="bold",
                color="#1F2937",
                zorder=5
            )

    ax.legend(loc="upper right", frameon=True, facecolor="#F9FAFB", edgecolor="#D1D5DB")

ax.set_title(f"Ternary Diagram: {mixture_label} ({basis_mode})", fontsize=13, fontweight="bold", pad=28, color="#111827")
ax.set_xlim(-0.14, 1.14)
ax.set_ylim(-0.13, H + 0.12)
ax.set_aspect("equal")
ax.axis("off")
plt.tight_layout()

# Save to PNG buffer
img_buf = io.BytesIO()
fig.savefig(img_buf, format="png", dpi=300, bbox_inches="tight")
img_buf.seek(0)

st.subheader("Ternary Plot & Envelope")
col_plot, col_table = st.columns([1.35, 1.0])

with col_plot:
    st.pyplot(fig, use_container_width=True)
    st.download_button(
        label="⬇️ Download Ternary Diagram (PNG)",
        data=img_buf,
        file_name=f"{mixture_label.lower().replace(' ', '_')}_ternary.png",
        mime="image/png",
        type="primary"
    )

with col_table:
    st.markdown("**Normalized Composition (%)**")
    if len(df_valid) > 0:
        display_cols = ["Label", "Pct_A", "Pct_B", "Pct_C"]
        renamed = df_valid[display_cols].rename(columns={
            "Pct_A": f"{comp_a} (%)",
            "Pct_B": f"{comp_b} (%)",
            "Pct_C": f"{comp_c} (%)"
        })
        st.dataframe(renamed, use_container_width=True, hide_index=True)
    else:
        st.info("Enter positive values (> 0) in at least one row to plot points.")
