
## 12. Larger synthetic dataset update

Following initial feedback, the dashboard was updated with a larger synthetic Greenhouse-like dataset to make the HR-facing demo more representative.

The larger dataset includes:

- 120 jobs;
- 1,800 candidates;
- 2,500 applications;
- several thousand application stage events;
- offers, recruiters, offices and departments linked consistently.

This dataset preserves the same structure as the original exercise data and keeps the same ingestion and transformation logic:

Mock Greenhouse API  
→ Workato API Sync Simulator  
→ BigQuery RAW  
→ dbt STAGING  
→ dbt CORE  
→ dbt MARTS  
→ Streamlit Dashboard  

The original files provided for the exercise are still preserved. The larger dataset is generated separately and can be selected through the mock API dataset profile.
