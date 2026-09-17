# Microzone Delineation Workflow  
[How-to Guide](https://docs.google.com/document/d/1gxxo6a0muU6JxEXwSgjpeitC1U00WUzy3vLYgeUYgp0/edit?tab=t.0)
[Fun Finds](https://docs.google.com/presentation/d/1QeFqcBgv2k-AAnNG6zQv8h4qFMt7IwfvOr7lrZEqdlo/edit?slide=id.p#slide=id.p)
[Group Activity](https://docs.google.com/presentation/d/1h45zvMTKtU1Hq30jq44Wj8s_6ZOTdFsKbvkwrldVKYw/edit?slide=id.p#slide=id.p)

## Requirements  
- **ArcGIS Pro**  
- **GitHub**  

## What is a Microzone?  
Microzones, or **Micro Analysis Zones (MAZ)**, are smaller than **Transportation Analysis Zones (TAZ)** and are used for finer-scale analyses.  

### Characteristics:  
- Typically the size of a **census block**  
- Comprised of similar **land use characteristics**:  
  - **Residential**  
  - **Commercial**  
  - **Industrial**  
  - **Education**  
  - **Parks & Open Space**  
  - **Greenspace**  
  - **Developed**  
- **Wasatch Choice Centers**  
- All buildings within a microzone may have **similar points of egress**  

---

## General Steps  

1. **Store all relevant project files** in a GitHub repository.  
2. **Clone** the repository into the **projects folder** on `ModelQueen`.  
3. Perform all microzone work within the **ArcGIS Pro project** inside the local repo.  
4. **Save edits frequently** and periodically **restart ArcGIS Pro** to prevent software issues.  
5. When finished:  
   - Save edits  
   - Save & close the ArcGIS Pro project (so others can open it)  
6. **Push the local repository** at the end of each workday where changes were made.  
7. Run **Microzones-Progress-Update.py** to get current progress

---

## How to Delineate Microzones  

### Supporting Data Layers  
The project includes several **data layers**:  
- **Nearmap 2024 Aerial Imagery** – Accessed via ArcGIS Online (flown last summer).  
- **TAZ Tracker** – Current **TAZ boundary** with tracking fields.  
- **Microzones Draft** – Pre-delineated zones based on TAZ, Wasatch Choice Centers, and road network.  
- **Land Use Dissolved** – 2019 REMM input buildings, dissolved by **building type**.  
- **Wasatch Choice Centers** – Walkable areas with mixed-use destinations, jobs, and housing.  
- **Road Centerlines** – Maintained by **UGRC**.  

### Editing Guidelines  
- **Microzones are pre-delineated**, but boundaries need adjustments.  
- Initial splits were made using:  
  - **TAZ boundaries**  
  - **Wasatch Choice Centers**  
  - **Utah Road Network**  
- However, **most splits are not meaningful** and require refinement.  
- Work on **one TAZ at a time**.  
- The **TAZ Tracker** dataset contains a column named `REVIEW` for tracking progress.  

### Key Questions for Splitting Microzones  
- **What types of land use** exist in the TAZ?  
- **How will traffic** within the zone access the **road network**?  

### ArcGIS Pro Editing Tools  
Use the following tools to adjust zones:  
- **Split** – Divides an existing zone along a user-drawn line.  
- **Merge** – Combines two or more zones into a single zone.  
- **Replace Polygon** – Allows complete redrawing of a polygon while maintaining TAZ outer boundaries.  

---

## Additional Considerations  
- **Do not alter the outer TAZ boundaries.** Microzones must remain within their TAZ.  
- **Keep shapes simple** – avoid:  
  - **Donut holes**  
  - **Unnecessary extrusions**  
- **Merging predefined zones** may be an option for creating desired zone shapes.  

---

## Tracking Progress  
Once a **MAZ has been reviewed**, update the `REVIEW` column with one of the following values:  

| Value | Description |  
|--------|--------------------------------|  
| **1** | Complete |  
| **2** | Needs further review |  