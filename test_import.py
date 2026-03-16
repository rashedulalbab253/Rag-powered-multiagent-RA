import sys
import pprint

print("Importing src.workflows.flow...")
try:
    import src.workflows.flow
    print("Successfully imported flow.py")
    
    print("Instantiating RAGPipeline...")
    from src.rag.rag_pipeline import RAGPipeline
    rag = RAGPipeline()
    print("RAGPipeline instantiated.")
    
except Exception as e:
    import traceback
    traceback.print_exc()
