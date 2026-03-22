# Auditoria Backend - Calia

## 🔍 Resumo Executivo

Auditoria completa do backend identificou **5 problemas críticos** e **8 melhorias recomendadas**.

---

## ⚠️ PROBLEMAS CRÍTICOS

### 1. **Endpoint POST /schools/with-admin SEM AUTENTICAÇÃO**
- **Localização**: `routers/schools.py`
- **Severidade**: 🔴 CRÍTICA
- **Descrição**: Permite criar escola com admin sem autenticação
- **Risco**: Qualquer pessoa pode criar escolas e contas admin
- **Solução**: Adicionar validação de autenticação

### 2. **Endpoint POST /users/reset-password SEM VALIDAÇÃO**
- **Localização**: `routers/users.py`
- **Severidade**: 🔴 CRÍTICA
- **Descrição**: Permite resetar senha sem verificar identidade
- **Risco**: Qualquer pessoa pode resetar senha de qualquer usuário
- **Solução**: Adicionar token de verificação por email

### 3. **Endpoint POST /students/upload SEM VALIDAÇÃO DE ARQUIVO**
- **Localização**: `routers/students.py`
- **Severidade**: 🟠 ALTA
- **Descrição**: Aceita upload de arquivo sem validar tipo/tamanho
- **Risco**: Possível upload de malware ou arquivo grande
- **Solução**: Validar tipo (CSV/XLSX) e tamanho máximo

### 4. **Endpoint GET /assessments/{id}/submissions RETORNA DADOS DE OUTRAS ESCOLAS**
- **Localização**: `routers/assessments.py` linha 195
- **Severidade**: 🟠 ALTA
- **Descrição**: Não filtra por `school_id`
- **Risco**: Usuário de uma escola pode ver dados de outra
- **Solução**: Adicionar filtro `.eq("school_id", user["school_id"])`

### 5. **Endpoint GET /dashboard/stats RETORNA DADOS DE TODAS AS ESCOLAS**
- **Localização**: `routers/dashboard.py`
- **Severidade**: 🟠 ALTA
- **Descrição**: Não filtra por `school_id`
- **Risco**: Usuário pode ver estatísticas de outras escolas
- **Solução**: Adicionar filtro `.eq("school_id", user["school_id"])`

---

## 🟠 PROBLEMAS ALTOS

### 6. **Falta Validação de Permissões em DELETE /assessments/{id}**
- **Localização**: `routers/assessments.py`
- **Severidade**: 🟠 ALTA
- **Descrição**: Qualquer professor pode deletar avaliação de outra turma
- **Solução**: Verificar se professor é dono da turma

### 7. **Falta Validação de Permissões em PUT /classes/{id}**
- **Localização**: `routers/classes.py`
- **Severidade**: 🟠 ALTA
- **Descrição**: Qualquer professor pode editar qualquer turma
- **Solução**: Verificar se professor é vinculado à turma

### 8. **Endpoint POST /ocr/correct NÃO VALIDA PERMISSÃO**
- **Localização**: `routers/ocr.py`
- **Severidade**: 🟠 ALTA
- **Descrição**: Qualquer professor pode corrigir prova de qualquer turma
- **Solução**: Verificar se professor é da turma

---

## 🟡 PROBLEMAS MÉDIOS

### 9. **Falta Tratamento de Erro em Endpoints**
- **Localização**: Múltiplos arquivos
- **Severidade**: 🟡 MÉDIA
- **Descrição**: Muitos endpoints retornam erro genérico
- **Solução**: Adicionar try-catch com mensagens específicas

### 10. **Falta Validação de Input em POST /assessments/create-full**
- **Localização**: `routers/assessments.py`
- **Severidade**: 🟡 MÉDIA
- **Descrição**: Não valida se questões têm resposta correta
- **Solução**: Validar estrutura de questões

### 11. **Endpoint GET /students/{id} NÃO EXISTE**
- **Localização**: `routers/students.py`
- **Severidade**: 🟡 MÉDIA
- **Descrição**: Frontend pode tentar acessar aluno específico
- **Solução**: Criar endpoint GET /students/{id}

### 12. **Falta Paginação em Endpoints de Lista**
- **Localização**: Múltiplos arquivos
- **Severidade**: 🟡 MÉDIA
- **Descrição**: Retorna todos os registros sem limite
- **Solução**: Adicionar `limit` e `offset` em queries

---

## ✅ PONTOS POSITIVOS

1. ✅ Todos os endpoints autenticados têm `get_current_user`
2. ✅ Filtro por `school_id` em endpoints principais
3. ✅ Validação de role (professor, admin, super_admin)
4. ✅ Tratamento de erro em OCR
5. ✅ Cálculo de score correto
6. ✅ Salvar `class_id` em submissões

---

## 📋 CHECKLIST DE CORREÇÕES

### CRÍTICAS (Fazer IMEDIATAMENTE)
- [ ] Adicionar autenticação em POST /schools/with-admin
- [ ] Adicionar validação em POST /users/reset-password
- [ ] Adicionar filtro `school_id` em GET /assessments/{id}/submissions
- [ ] Adicionar filtro `school_id` em GET /dashboard/stats

### ALTAS (Fazer antes de deploy)
- [ ] Validar permissões em DELETE /assessments/{id}
- [ ] Validar permissões em PUT /classes/{id}
- [ ] Validar permissões em POST /ocr/correct
- [ ] Validar tipo/tamanho de arquivo em POST /students/upload

### MÉDIAS (Fazer em próxima sprint)
- [ ] Adicionar try-catch em todos os endpoints
- [ ] Validar input em POST /assessments/create-full
- [ ] Criar endpoint GET /students/{id}
- [ ] Adicionar paginação em endpoints de lista

---

## 🔐 Recomendações de Segurança

1. **Rate Limiting**: Adicionar limite de requisições por IP
2. **CORS**: Configurar CORS apenas para domínio permitido
3. **SQL Injection**: Usar sempre Supabase ORM (já está fazendo)
4. **HTTPS**: Garantir que API está em HTTPS
5. **Tokens**: Implementar refresh token com expiração
6. **Logs**: Adicionar logs de auditoria para ações críticas

---

## 📊 Status Geral

| Categoria | Status | Ações |
|-----------|--------|-------|
| Autenticação | ✅ Bom | Nenhuma |
| Autorização | ⚠️ Precisa Melhorar | 4 correções críticas |
| Validação | ⚠️ Precisa Melhorar | 3 correções altas |
| Tratamento de Erro | ⚠️ Precisa Melhorar | 1 correção média |
| Segurança | ⚠️ Precisa Melhorar | 6 recomendações |

**Conclusão**: Backend está **70% pronto** para mercado. Precisa corrigir problemas de segurança antes de deploy.
