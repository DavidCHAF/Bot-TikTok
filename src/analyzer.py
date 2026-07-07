from typing import List, Dict, Any

def get_top_trends(data_t1: List[Dict[str, Any]], data_t2: List[Dict[str, Any]], delta_t_hours: float) -> List[Dict[str, Any]]:
    """
    Compare deux états de données (T1 et T2) en appliquant les formules mathématiques.
    Filtre les vidéos selon des paliers (tiers) stricts basés sur les vues initiales (V_T1)
    et la croissance relative (C_r).
    """
    trends = []
    
    # Dictionnaire pour un accès rapide aux données T1
    t1_dict = {item['id']: item for item in data_t1}
    
    for item_t2 in data_t2:
        vid_id = item_t2['id']
        if vid_id in t1_dict:
            item_t1 = t1_dict[vid_id]
            
            # Variables de base
            v_t1 = int(item_t1.get('views', 0))
            v_t2 = int(item_t2.get('views', 0))
            delta_likes = int(item_t2.get('likes', 0)) - int(item_t1.get('likes', 0))
            delta_coms = int(item_t2.get('comments', 0)) - int(item_t1.get('comments', 0))
            delta_partages = int(item_t2.get('shares', 0)) - int(item_t1.get('shares', 0))
            
            # 1. Vélocité Linéaire Brute (Gain net)
            delta_v = v_t2 - v_t1
            
            # 2. Vélocité Horaire (Standardisation du temps)
            v_h = delta_v / delta_t_hours if delta_t_hours > 0 else 0
            
            # 3. Taux de Croissance Relatif (Détection d'anomalie)
            if v_t1 == 0:
                c_r = 100.0 if delta_v > 0 else 0.0 # Si ça passe de 0 à quelque chose, grosse croissance
            else:
                c_r = (delta_v / v_t1) * 100
                
            # 4. Score de Vélocité Pondéré (Algorithme de tri final)
            score = (v_h * 0.4) + (delta_likes * 0.3) + (delta_coms * 0.2) + (delta_partages * 0.1)
            
            # Filtrage Dynamique par Tiers (Thresholds)
            keep = False
            if v_t1 < 500:
                keep = False
            elif 500 <= v_t1 < 10000:
                keep = c_r >= 200
            elif 10000 <= v_t1 < 100000:
                keep = c_r >= 100
            elif v_t1 >= 100000:
                keep = c_r >= 30
                
            if keep:
                trends.append({
                    'id': vid_id,
                    'url': item_t2.get('url', ''),
                    'title': item_t2.get('title', ''),
                    'description': item_t2.get('description', item_t1.get('description', '')),
                    'views_t1': v_t1,
                    'views_t2': v_t2,
                    'delta_v': delta_v,
                    'v_h': v_h,
                    'c_r': c_r,
                    'score': score
                })
            
    # Trier par Score décroissant (les meilleures en premier)
    trends.sort(key=lambda x: x['score'], reverse=True)
    
    return trends
