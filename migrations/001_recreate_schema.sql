-- ============================================================================
-- SCRIPT DE MIGRAÇÃO: RECRIAR ESTRUTURA COMPLETA DO SUPABASE
-- ============================================================================
-- Este script deleta todas as tabelas antigas e cria uma nova estrutura
-- otimizada com constraints, foreign keys e índices.
-- ============================================================================

-- Desabilitar verificação de foreign keys temporariamente
SET session_replication role = 'replica';

-- ============================================================================
-- 1. DELETAR TABELAS ANTIGAS (se existirem)
-- ============================================================================

DROP TABLE IF EXISTS student_submissions CASCADE;
DROP TABLE IF EXISTS assessment_questions CASCADE;
DROP TABLE IF EXISTS assessments CASCADE;
DROP TABLE IF EXISTS teacher_classes CASCADE;
DROP TABLE IF EXISTS teacher_subjects CASCADE;
DROP TABLE IF EXISTS subjects CASCADE;
DROP TABLE IF EXISTS classes CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS schools CASCADE;

-- ============================================================================
-- 2. CRIAR TABELA: SCHOOLS (Escolas)
-- ============================================================================

CREATE TABLE schools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_schools_slug ON schools(slug);

-- ============================================================================
-- 3. CRIAR TABELA: PROFILES (Usuários - Super Admin, Admin, Professor, Aluno)
-- ============================================================================

CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('super_admin', 'admin', 'professor', 'aluno')),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_profiles_school_id ON profiles(school_id);
CREATE INDEX idx_profiles_role ON profiles(role);
CREATE INDEX idx_profiles_email ON profiles(email);

-- ============================================================================
-- 4. CRIAR TABELA: CLASSES (Turmas)
-- ============================================================================

CREATE TABLE classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    year_level INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_classes_school_id ON classes(school_id);

-- ============================================================================
-- 5. CRIAR TABELA: STUDENTS (Alunos)
-- ============================================================================

CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    registration_number VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'CURSANDO' CHECK (status IN ('CURSANDO', 'TRANSFERIDO', 'EVADIDO', 'FORMADO')),
    birth_date DATE,
    cpf VARCHAR(14) UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_students_school_id ON students(school_id);
CREATE INDEX idx_students_class_id ON students(class_id);
CREATE INDEX idx_students_user_id ON students(user_id);
CREATE INDEX idx_students_email ON students(email);
CREATE INDEX idx_students_registration ON students(registration_number);

-- ============================================================================
-- 6. CRIAR TABELA: SUBJECTS (Disciplinas)
-- ============================================================================

CREATE TABLE subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_subjects_school_id ON subjects(school_id);

-- ============================================================================
-- 7. CRIAR TABELA: TEACHER_SUBJECTS (Disciplinas do Professor)
-- ============================================================================

CREATE TABLE teacher_subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(teacher_id, subject_id)
);

CREATE INDEX idx_teacher_subjects_teacher_id ON teacher_subjects(teacher_id);
CREATE INDEX idx_teacher_subjects_subject_id ON teacher_subjects(subject_id);

-- ============================================================================
-- 8. CRIAR TABELA: TEACHER_CLASSES (Turmas do Professor)
-- ============================================================================

CREATE TABLE teacher_classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(teacher_id, class_id)
);

CREATE INDEX idx_teacher_classes_teacher_id ON teacher_classes(teacher_id);
CREATE INDEX idx_teacher_classes_class_id ON teacher_classes(class_id);

-- ============================================================================
-- 9. CRIAR TABELA: ASSESSMENTS (Avaliações)
-- ============================================================================

CREATE TABLE assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    class_id UUID NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES subjects(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    assessment_type VARCHAR(50) DEFAULT 'PROVA' CHECK (assessment_type IN ('PROVA', 'TRABALHO', 'PROJETO', 'PARTICIPACAO')),
    total_questions INTEGER DEFAULT 0,
    total_points DECIMAL(5,2) DEFAULT 10.0,
    is_published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_assessments_school_id ON assessments(school_id);
CREATE INDEX idx_assessments_class_id ON assessments(class_id);
CREATE INDEX idx_assessments_subject_id ON assessments(subject_id);
CREATE INDEX idx_assessments_created_by ON assessments(created_by);

-- ============================================================================
-- 10. CRIAR TABELA: ASSESSMENT_QUESTIONS (Questões da Avaliação)
-- ============================================================================

CREATE TABLE assessment_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL,
    correct_answer VARCHAR(10) NOT NULL,
    weight DECIMAL(5,2) DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_assessment_questions_assessment_id ON assessment_questions(assessment_id);

-- ============================================================================
-- 11. CRIAR TABELA: STUDENT_SUBMISSIONS (Submissões de Alunos)
-- ============================================================================

CREATE TABLE student_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id UUID NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    extracted_answers JSONB NOT NULL DEFAULT '{}',
    score DECIMAL(5,2),
    is_final BOOLEAN DEFAULT FALSE,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_student_submissions_school_id ON student_submissions(school_id);
CREATE INDEX idx_student_submissions_assessment_id ON student_submissions(assessment_id);
CREATE INDEX idx_student_submissions_student_id ON student_submissions(student_id);
CREATE INDEX idx_student_submissions_uploaded_by ON student_submissions(uploaded_by);

-- ============================================================================
-- 12. REABILITAR VERIFICAÇÃO DE FOREIGN KEYS
-- ============================================================================

SET session_replication role = 'origin';

-- ============================================================================
-- 13. CRIAR VIEWS ÚTEIS
-- ============================================================================

-- View: Professores com suas informações
CREATE VIEW v_teachers AS
SELECT 
    p.id,
    p.school_id,
    p.full_name,
    p.email,
    p.phone,
    p.is_active,
    p.created_at
FROM profiles p
WHERE p.role = 'professor';

-- View: Alunos com suas informações e turma
CREATE VIEW v_students_with_class AS
SELECT 
    s.id,
    s.school_id,
    s.class_id,
    s.name,
    s.email,
    s.registration_number,
    s.status,
    c.name as class_name,
    s.is_active,
    s.created_at
FROM students s
LEFT JOIN classes c ON s.class_id = c.id;

-- ============================================================================
-- FIM DO SCRIPT
-- ============================================================================
