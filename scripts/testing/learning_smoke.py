"""Exercise native estimators, sparse paths and OpenMP threads on Android."""

import importlib.metadata
import json
import os
import sys
import tempfile
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.utils._openmp_helpers import (
    _openmp_effective_n_threads,
    _openmp_parallelism_enabled,
)
from threadpoolctl import threadpool_info, threadpool_limits


def main() -> None:
    assert hasattr(sys, "getandroidapilevel")
    assert _openmp_parallelism_enabled()
    assert _openmp_effective_n_threads(2) == 2
    x = np.array(
        [[i / 10, i / 20] for i in range(6)]
        + [[5 + i / 10, 5 + i / 20] for i in range(6)]
    )
    y = np.repeat([0, 1], 6)
    with threadpool_limits(limits=2), joblib.parallel_backend("threading", n_jobs=2):
        scaled = StandardScaler().fit_transform(x)
        np.testing.assert_allclose(scaled.mean(axis=0), 0, atol=1e-15)
        pipeline = make_pipeline(
            StandardScaler(), LogisticRegression(C=10, random_state=0)
        )
        pipeline.fit(x, y)
        np.testing.assert_array_equal(pipeline.predict(x), y)
        np.testing.assert_allclose(pipeline.predict_proba(x).sum(axis=1), 1)
        clustering = KMeans(n_clusters=2, n_init=5, random_state=0).fit(x)
        assert silhouette_score(x, clustering.labels_) > 0.9
        decomposition = PCA(n_components=1).fit(x)
        assert decomposition.explained_variance_ratio_.sum() > 0.99
        forest = RandomForestClassifier(n_estimators=16, random_state=0, n_jobs=2).fit(
            x, y
        )
        np.testing.assert_array_equal(forest.predict(x), y)
        boosting = HistGradientBoostingClassifier(
            max_iter=30, min_samples_leaf=2, random_state=0
        ).fit(x, y)
        np.testing.assert_array_equal(boosting.predict(x), y)
        np.testing.assert_array_equal(
            SVC(kernel="linear", C=10).fit(x, y).predict(x), y
        )
        sparse = csr_matrix(x)
        np.testing.assert_array_equal(
            LogisticRegression(C=10).fit(sparse, y).predict(sparse), y
        )
        distances, indices = (
            NearestNeighbors(n_neighbors=1, algorithm="kd_tree").fit(x).kneighbors(x)
        )
        np.testing.assert_array_equal(indices.ravel(), np.arange(len(x)))
        np.testing.assert_allclose(distances, 0)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "model.joblib"
            joblib.dump(pipeline, path)
            np.testing.assert_array_equal(joblib.load(path).predict(x), y)
        pools = threadpool_info()
        assert any(p["internal_api"] == "openmp" for p in pools)
    print(
        json.dumps(
            {
                "python": sys.version,
                "python_minimum_api": sys.getandroidapilevel(),
                "machine": os.uname().machine,
                "page_size": os.sysconf("SC_PAGE_SIZE"),
                "versions": {
                    name: importlib.metadata.version(name)
                    for name in [
                        "numpy",
                        "scipy",
                        "scikit-learn",
                        "joblib",
                        "narwhals",
                        "threadpoolctl",
                    ]
                },
                "threadpools": pools,
                "checks": [
                    "openmp_enabled",
                    "openmp_two_threads",
                    "scaling",
                    "pipeline_logistic",
                    "probabilities",
                    "kmeans",
                    "pca",
                    "random_forest_threads",
                    "hist_gradient_boosting",
                    "svm",
                    "sparse_logistic",
                    "kd_tree",
                    "joblib_roundtrip",
                ],
                "result": "passed",
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
