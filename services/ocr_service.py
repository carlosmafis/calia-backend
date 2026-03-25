# services/ocr_service.py

import cv2
import numpy as np
from PIL import Image, ImageOps


# ==========================
# FUNÇÃO PARA ORDENAR PONTOS (PERSPECTIVA)
# ==========================

def order_points(pts):

    rect = np.zeros((4,2), dtype="float32")

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


# ==========================
# FUNÇÃO PRINCIPAL OCR
# ==========================

def read_answer_sheet(image_path, gabarito):

    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)

    img = np.array(image)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    h, w = img.shape[:2]

    altura_max = 1000

    if h > altura_max:

        proporcao = altura_max / h
        novo_w = int(w * proporcao)

        img = cv2.resize(img, (novo_w, altura_max))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Usar Harris corner detection para encontrar os 4 cantos
    corners = cv2.cornerHarris(gray, 2, 3, 0.04)
    
    # Normalizar e threshold
    corners = cv2.normalize(corners, None)
    corners = (corners * 255).astype(np.uint8)
    
    # Encontrar os pontos de canto
    ret, corners_binary = cv2.threshold(corners, 127, 255, cv2.THRESH_BINARY)
    
    # Encontrar contornos dos cantos
    contours, _ = cv2.findContours(corners_binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    h_img, w_img = img.shape[:2]
    
    # Definir regiões de busca para cada canto (20% de cada lado)
    corner_regions = {
        'tl': (0, int(w_img * 0.2), 0, int(h_img * 0.2)),
        'tr': (int(w_img * 0.8), w_img, 0, int(h_img * 0.2)),
        'bl': (0, int(w_img * 0.2), int(h_img * 0.8), h_img),
        'br': (int(w_img * 0.8), w_img, int(h_img * 0.8), h_img)
    }
    
    corner_points = {}
    
    for region_name, (x1, x2, y1, y2) in corner_regions.items():
        # Procurar o ponto mais forte nesta região
        region_corners = corners[y1:y2, x1:x2]
        
        if region_corners.size > 0:
            # Encontrar o ponto com maior valor de corner
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(region_corners)
            
            if max_val > 0:
                # Converter para coordenadas globais
                cy = max_loc[1] + y1
                cx = max_loc[0] + x1
                corner_points[region_name] = (cx, cy)
    
    # Se não encontrou todos os 4 cantos, tentar estratégia alternativa
    if len(corner_points) < 4:
        # Estratégia alternativa: procurar por bordas e depois por cantos
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        
        # Dilatação para conectar bordas
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges = cv2.dilate(edges, kernel, iterations=2)
        
        # Encontrar contornos das bordas
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        corner_points = {}
        
        for region_name, (x1, x2, y1, y2) in corner_regions.items():
            best_point = None
            best_distance = float('inf')
            
            for cnt in contours:
                M = cv2.moments(cnt)
                if M["m00"] == 0:
                    continue
                
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Verificar se está na região
                if x1 <= cx < x2 and y1 <= cy < y2:
                    # Calcular distância até o canto esperado
                    if region_name == 'tl':
                        expected = (x1, y1)
                    elif region_name == 'tr':
                        expected = (x2, y1)
                    elif region_name == 'bl':
                        expected = (x1, y2)
                    else:  # br
                        expected = (x2, y2)
                    
                    dist = np.sqrt((cx - expected[0])**2 + (cy - expected[1])**2)
                    
                    if dist < best_distance:
                        best_distance = dist
                        best_point = (cx, cy)
            
            if best_point:
                corner_points[region_name] = best_point
    
    if len(corner_points) < 4:
        raise Exception("Marcadores não detectados")
    
    # Montar array de pontos na ordem correta
    pts = np.array([
        corner_points['tl'],
        corner_points['tr'],
        corner_points['br'],
        corner_points['bl']
    ], dtype="float32")

    rect = order_points(pts)

    warped = cv2.warpPerspective(
        img,
        cv2.getPerspectiveTransform(
            rect,
            np.array([[0,0],[599,0],[599,899],[0,899]], dtype="float32")
        ),
        (600,900)
    )

    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    respostas_detectadas = []

    altura_total, largura_total = gray.shape

    top = int(altura_total * 0.11)
    bottom = int(altura_total * 0.92)
    left = int(largura_total * 0.18)
    right = int(largura_total * 0.91)

    grade = gray[top:bottom, left:right]

    # overlay agora é a folha inteira
    debug_overlay = warped.copy()

    h_grade, w_grade = grade.shape

    altura_linha = h_grade / 10.0

    posicoes_colunas = [0.235,0.370,0.505,0.640,0.775]

    raio = int(w_grade * 0.045)

    for i in range(len(gabarito)):

        alternativas = []
        centros = []

        for pos in posicoes_colunas:

            centro_x = int(w_grade * pos)
            centro_y = int(round((i + 0.39) * altura_linha))

            x1 = max(centro_x - raio,0)
            x2 = min(centro_x + raio,w_grade)

            y1 = max(centro_y - raio,0)
            y2 = min(centro_y + raio,h_grade)

            celula = grade[y1:y2, x1:x2]

            media_intensidade = np.mean(celula)

            alternativas.append(media_intensidade)
            centros.append((centro_x, centro_y))

        media = np.mean(alternativas)
        desvio = np.std(alternativas)

        limiar = media - (0.6 * desvio)

        marcadas = [
            idx for idx,valor in enumerate(alternativas)
            if valor < limiar
        ]

        if len(marcadas) == 0:

            respostas_detectadas.append("BRANCO")

        elif len(marcadas) > 1:

            respostas_detectadas.append("ANULADA")

            for idx in marcadas:
                cx, cy = centros[idx]

                cv2.circle(
                    debug_overlay,
                    (cx + left, cy + top),
                    raio,
                    (0,255,255),
                    3
                )

        else:

            idx = marcadas[0]

            respostas_detectadas.append(
                ["A","B","C","D","E"][idx]
            )

            cx, cy = centros[idx]

            cv2.circle(
                debug_overlay,
                (cx + left, cy + top),
                raio,
                (0,255,0),
                3
            )

        # número da questão
        cv2.putText(
            debug_overlay,
            str(i+1),
            (int(w_grade*0.05)+left, int((i+0.5)*altura_linha)+top),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255,0,0),
            2
        )

    answers_dict = {}

    for i,resp in enumerate(respostas_detectadas):
        answers_dict[str(i+1)] = resp

    import base64

    _, buffer = cv2.imencode(".jpg", debug_overlay)
    debug_base64 = base64.b64encode(buffer).decode()

    return {
        "answers": answers_dict,
        "debug_image": debug_base64
    }
