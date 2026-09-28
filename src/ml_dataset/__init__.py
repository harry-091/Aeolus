"""Phase 3: Machine Learning Training Dataset Generation.

Dedicated, leak-free supervised dataset extraction pipeline for polar maritime navigation.
Processes historical AIS and environmental replay observations into normalized feature
vectors and aligned navigation targets, strictly partitioned by voyage.
"""

from .feature_extractor import FeatureExtractor, MLFeatureVector
from .target_generator import TargetGenerator, MLTargetVector
from .voyage_splitter import VoyageSplitter, DatasetSplits
from .dataset_generator import MLDatasetGenerator, DatasetSummary

__all__ = [
    "FeatureExtractor",
    "MLFeatureVector",
    "TargetGenerator",
    "MLTargetVector",
    "VoyageSplitter",
    "DatasetSplits",
    "MLDatasetGenerator",
    "DatasetSummary",
]
