import numpy as np
from sklearn.cluster import KMeans

def test_clustering():
    # Praat Medians for the segments
    praat_medians = [247.1, 146.8, 277.6, 212.3]
    segments = [
        {"start": 0.0, "end": 0.9},
        {"start": 0.9, "end": 1.4},
        {"start": 1.4, "end": 2.1},
        {"start": 2.1, "end": 2.6}
    ]
    
    # 1. Clustering
    X = np.array(praat_medians).reshape(-1, 1)
    
    # If the variance is very low, it might be a single speaker
    if np.std(praat_medians) < 30: # 30Hz difference is typical for single speaker variance
        mean_pitch = np.mean(praat_medians)
        gender = "female" if mean_pitch > 175 else "male"
        print(f"Single speaker detected (Mean {mean_pitch:.1f}Hz): {gender}")
    else:
        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10).fit(X)
        
        # 2. Assign Gender to Clusters based on their Centers
        cluster_centers = kmeans.cluster_centers_.flatten()
        
        if cluster_centers[0] > cluster_centers[1]:
            female_cluster = 0
            male_cluster = 1
        else:
            female_cluster = 1
            male_cluster = 0
            
        # 3. Assign
        for i, pitch in enumerate(praat_medians):
            c = kmeans.labels_[i]
            gender = "female" if c == female_cluster else "male"
            print(f"Segment {i+1} ({pitch:.1f}Hz) -> {gender}")

test_clustering()
