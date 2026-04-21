-- docker/init.sql
-- PostgreSQL 首次初始化脚本（仅在 volume 为空时执行一次）
--
-- 作用：启用必要扩展 + 创建基础配置
-- schema 的 CREATE TABLE 由 alembic migration 负责，不放在这里

-- ================================================================
-- 1. 启用扩展
-- ================================================================

-- pg_trgm: 三元组模糊匹配（公司简称 fallback、型号简称 fallback）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- uuid-ossp: 生成 UUID（虽然 PG 16 有 gen_random_uuid()，但老代码兼容）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- pgcrypto: 如果后续需要加密（如敏感字段脱敏）
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ================================================================
-- 2. 默认配置
-- ================================================================

-- 时区统一为东八区
ALTER DATABASE erp_ai SET timezone TO 'Asia/Shanghai';

-- 搜索路径（暂时只用 public，后续可能分 schema）
ALTER DATABASE erp_ai SET search_path TO public;

-- ================================================================
-- 3. 创建只读账号（审计/BI 查询用，暂时预留）
-- ================================================================
-- 注意：实际创建等 alembic 建完表后，再执行 scripts/create_readonly_user.sql

-- ================================================================
-- 4. 提示信息
-- ================================================================
DO $$
BEGIN
    RAISE NOTICE '=================================================';
    RAISE NOTICE 'ERP AI 数据库初始化完成';
    RAISE NOTICE '扩展: pg_trgm, uuid-ossp, pgcrypto 已启用';
    RAISE NOTICE '时区: Asia/Shanghai';
    RAISE NOTICE '下一步: 运行 alembic upgrade head 建表';
    RAISE NOTICE '=================================================';
END $$;
