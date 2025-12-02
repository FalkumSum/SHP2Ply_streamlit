import io
import zipfile
import tempfile
from pathlib import Path

import geopandas as gpd
import streamlit as st


def geodf_to_ply_string(gdf):
    buf = io.StringIO()
    poly_counter = 1

    for geom in gdf.geometry:
        if geom is None:
            continue

        if geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        elif geom.geom_type == "Polygon":
            polygons = [geom]
        else:
            continue

        for poly in polygons:
            buf.write("poly {}\n".format(poly_counter))
            x, y = poly.exterior.xy
            for xi, yi in zip(x, y):
                buf.write("   {:.2f}   {:.2f} \n".format(xi, yi))
            buf.write("\n")
            poly_counter += 1

    return buf.getvalue()


def print_gdf_details_to_streamlit(gdf):
    st.subheader("GeoDataFrame details")
    st.write("Raw CRS:", gdf.crs)

    epsg = None
    if gdf.crs is not None:
        try:
            epsg = gdf.crs.to_epsg()
        except Exception:
            epsg = None

    st.write("Detected EPSG:", epsg if epsg is not None else "Unknown")

    if gdf.crs is not None:
        st.write("CRS WKT snippet:")
        st.text(gdf.crs.to_wkt()[:400] + "...")
    else:
        st.write("CRS WKT snippet: None")

    st.write("Columns:", list(gdf.columns))
    st.write("Geometry types:", gdf.geometry.geom_type.value_counts())
    st.write("Total features:", len(gdf))
    st.write("Bounds:", gdf.total_bounds)
    st.write("Head():")
    st.write(gdf.head())


def load_shapefile_from_zip(uploaded_zip):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        zip_path = tmpdir / "upload.zip"

        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        shp_files = list(tmpdir.rglob("*.shp"))
        if not shp_files:
            raise FileNotFoundError("ZIP does not contain a .shp file")

        return gpd.read_file(shp_files[0])


def main():
    st.title("SHP → Geosoft PLY Converter (Streamlit Cloud)")

    st.write(
        "Upload a **zipped shapefile** (all files: .shp, .shx, .dbf, .prj). "
        "The app will detect the CRS, allow reprojection, and export as Geosoft .ply."
    )

    uploaded_zip = st.file_uploader("Upload ZIP shapefile", type=["zip"])

    if uploaded_zip is None:
        st.info("Please upload a zipped shapefile.")
        return

    # Load SHP from ZIP
    try:
        gdf = load_shapefile_from_zip(uploaded_zip)
    except Exception as e:
        st.error("Failed to read shapefile: {}".format(e))
        return

    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    if gdf.empty:
        st.error("No Polygon or MultiPolygon features found in the shapefile.")
        return

    print_gdf_details_to_streamlit(gdf)

    epsg_detected = None
    if gdf.crs is not None:
        try:
            epsg_detected = gdf.crs.to_epsg()
        except Exception:
            epsg_detected = None

    default_epsg = epsg_detected if epsg_detected is not None else 4326

    st.subheader("Output settings")

    output_epsg = st.number_input("Output EPSG", value=int(default_epsg), step=1)
    output_filename = st.text_input("Output PLY file name", value="output.ply")

    if st.button("Convert to PLY"):
        try:
            gdf_out = gdf.to_crs(epsg=int(output_epsg))
        except Exception as e:
            st.error("Error reprojecting: {}".format(e))
            return

        ply_text = geodf_to_ply_string(gdf_out)

        st.success("PLY conversion successful")

        preview = "\n".join(ply_text.splitlines()[:50])
        st.subheader("Preview (first 50 lines)")
        st.code(preview)

        st.download_button(
            "Download PLY",
            data=ply_text.encode("utf-8"),
            file_name=output_filename,
            mime="text/plain"
        )


if __name__ == "__main__":
    main()
