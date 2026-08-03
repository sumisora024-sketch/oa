主旨
    1.构建一个在日华人公司内部的oa系统，内容包括人员管理，契约管理，案件管理这三个业务模块，其他基础模块参照成熟开源项目如登录等。
    2.参考国内的oa系统设计，前端使用element ui国际化多语言框架，后端使用python fastapi 或者golang gin 框架，中间件使用mysql和redis。
    3.前端需要路由鉴权，后端需要jwt鉴权，不同权限所见或者所渲染的ui不同。
    4.将所有环境变量，中间件连接串，apikey，公共邮箱信息独立为.env文件
    5.中间件 只需要admin信息即可，不在需要rw schema权限鉴定。
    redis 无需密码，mysql初始用户密码 admin admin123. 
详细设计
    1.登录模块 homepage模块
        1.1分为admin，hr，pm营业，一般员工。   
            admin可以read write new delete所有接口映射的页面 所有人员管理 契约 案件信息。
            hr可以rwnd 人员管理 契约管理的所有信息 。 
            pm营业可以rwnd所有案件管理的信息，可以r 所有人员信息。
            一般员工 只能r 自己的一般员工信息（非人员管理模块 api借用） ，r 自己的契约信息。
            所有员工登进去后先进入homepage模块，可以看到自己的个人信息，契约信息，所在案件项目信息。然后有权限的角色可以在ui选到对应的管理模块。
        1.2 使用jwt鉴权，中间态 session cookie持续15分钟，可以发行aurthor信息，方便后续调用本系统api，中间session加密信息放在redis。
        1.3 新建删除人员功能，只能admin操作。
        1.4 根据邮箱重置密码功能，发送重置link给系统已经存在的邮箱，充值密码。
        1.5 可以通过ms teams的sso邮箱登录，默认为一般员工（如果能通过sso取到信息就映射上去，设想 不能实现告诉我）
        1.6 默认其他所需模块参考市面成熟系统，浏览器等干涉行为参考业内成熟系统。

    2.人员管理
        2.1基础属性 姓名，日文假名，出生年月日，毕业状态，居住地，最近的车站，邮箱，电话，年龄，语言能力，证书，技术经历，it工龄，人才分类（infra，前端，后端），技能技术栈罗列（aws，java，golang，azure 加高 中 低评价）
        2.2功能模块 请参照1.xlsx的详细内容 并且记录入库，要求上传xlsx能将信息载入基础信息
        2.3新建人员功能，要求能够自己新建人员，手动填写属性，其中出生年月日，毕业状态，居住地，最近的车站，邮箱，电话，年龄为必填项。
        2.4可以下载自己的在职信息，
    3.契约管理
        3.1 契约信息 能够读取pdf，参考1.pdf 将其映射为基础属性。
        3.2 属性为契约社员情况下 提前一个月在邮箱发邮件提醒hr和本人
    4.案件管理
        4.1我会配置一个邮箱，新建一个mq，监听邮件到mail事件，异步处理
        4.2 接入ai分析模块（openai apikey module 5.5），将邮件内容案件拆解为元数据信息 ：甲方公司名，案件项目名，案件描述，所需技术栈list，工作场所（全在宅，半在宅，出勤地点），候选人国籍要求，项目时长（长期，短浅 从xx开始到xx终了），所需人员数，单价。    
            映射不到的填空，只有甲方公司名，案件项目名，案件描述，所需技术栈list，工作场所这几项在数据库为非空
            有附件以附件为准，没有附件以邮件信息为准。
        4.3 推荐候选人模块，根据项目信息匹配候选人，按权重计算候选人分数。通过模块，将读取数据库候选人信息，存到redis，ai读取redis信息，通过权重计算分数，列出最匹配的人选。
            如果有国籍10，没有0.技术栈权重6，工作年龄权重2，居住地权重2。
            总结4.3 写成promt，每次调用api给提示词。

接口文档（当前实现摘要）
    1.认证与首页
        POST /api/auth/login 登录，POST /api/auth/password/change 首次登录或登录后用户主动修改密码，POST /api/auth/password/reset-request 与 POST /api/auth/password/reset-confirm 为邮件 link 自助重置密码接口，受 PASSWORD_RESET_EMAIL_ENABLED 开关控制，当前默认关闭。GET /api/homepage 返回当前用户、权限、个人信息、当前契约、当前月工资、所在案件；三方 partner 返回三方公司信息和静态会社介绍，不展示内部员工主页。
    2.人员管理
        GET/POST/PUT/DELETE /api/employees，POST /api/employees/import-xlsx，POST /api/employees/{employee_id}/password/reset 管理员重置员工平台账号密码为 DEFAULT_EMPLOYEE_PASSWORD 并强制下次登录改密。新建或导入新员工成功后自动创建平台账号，账号规则为 姓拼音_名拼音@nit-g.co.jp，初始密码来自 DEFAULT_EMPLOYEE_PASSWORD，首次登录必须重置密码。删除为逻辑删除，列表默认不展示；使用同邮箱再次新建时恢复原人员和原平台账号，避免生成 xxx2@nit-g.co.jp。
        GET/POST/PUT/DELETE /api/external-personnel 管理外部入场人员，POST /api/external-personnel/{id}/status 确认/拒绝外部人员，GET /api/external-personnel/{id}/files/{kind}/download 下载简历、头像、工时表。新建外部入场人员时 CV 和 PNG 头像为必填。
    3.契约管理
        GET/POST/PUT/DELETE /api/contracts，POST /api/contracts/import-pdf。
        GET /api/contracts/salaries 按年月生成/查询工资记录，PUT /api/contracts/salaries/{record_id} 更新月度工时、工时段、年金、住民税、保险费用、当月支给工资、想定年収和工资锁定状态。
        GET /api/contracts/salaries/self 按年月查询当前员工自己的工资明细；GET /api/contracts/salaries/{record_id}/payslip.pdf 下载工资明细 PDF；GET /api/contracts/salaries/{record_id}/annual-estimate.pdf 下载想定年収 PDF。
    4.案件管理
        GET/POST/PUT/DELETE /api/projects，POST /api/projects/analyze-email，POST /api/projects/mailbox/poll。
        GET /api/projects/assignments 查询案件归属，POST /api/projects/{project_id}/assignments 分配人员，GET /api/projects/{project_id}/recommendations 推荐候选人。
    5.系统设置
        GET/PUT /api/settings/mail，POST /api/settings/mail/test-imap，POST /api/settings/mail/test-smtp。
    6.外部契约管理
        GET/POST/PUT/DELETE /api/external/partners 管理已缔结公司/取引先。
        GET/POST/PUT /api/external/contracts 管理外部契约记录，POST /api/external/contracts/upload 上传上家或下家契约文件。
        下家或 both 新缔结成功后自动生成三方 partner 登录账号，账号为 users.login_id，格式 NIT_PARTNER_公司名或公司假名发音，初始密码随机生成，仅在创建响应中返回一次。
        GET /api/external/fixed-files 查询 NIT-1 到 NIT-5 固定文件，GET /api/external/fixed-files/{file_id}/download 后台下载固定文件，GET /api/external/fixed-files/download-all 打包下载五个固定文件；当前后台 UI 不展示 NIT-1 到 NIT-5 快捷按钮，三方下载入口放在准委任的公司须知/声明。
        GET /api/external/public/contracts/{token}/fixed-files 与 GET /api/external/public/contracts/{token}/fixed-files/{file_id} 为下家新缔结契约生成 demo 下载 link；GET /api/external/public/contracts/{token}/fixed-files/download-all 提供公共打包下载 link。
        POST /api/external/purchase-orders 根据审批通过的三方見積書生成发注书 PDF，POST /api/external/quotations 生成見積書 Excel，POST /api/external/invoices/from-quotation/{quotation_id} 由見積書生成请求书 PDF。
        GET /api/external/partner-quotations/approved 查询审批通过的三方見積書，供发注书生成下拉选择。
        PUT /api/external/documents/{document_id}/settlement 由 admin 更新请求书实收或发注书实付状态和金额。
        GET /api/external/documents 查询生成/上传书类，GET /api/external/documents/{document_id}/download 下载本地文件，DELETE /api/external/documents/{document_id} 逻辑删除书类记录。
        GET /api/external/settlements/{year_month} 按 target_month 汇总请求书、发注书、工资并生成月度结算，返回请求书/发注书明细。
    7.准委任/审批
        GET /api/subcontracting/quotations 查询三方提交的見積書，POST /api/subcontracting/quotations/upload 上传三方原始見積書文件并自动创建审批流；partner 登录时 partner_id 由 users.partner_id 自动确定，admin 调用时需要显式传入 partner_id。旧版 POST /api/subcontracting/quotations 保留兼容结构化生成，但前端不再使用。
        GET /api/subcontracting/fixed-files、GET /api/subcontracting/fixed-files/{file_id}/download、GET /api/subcontracting/fixed-files/download-all 提供公司须知/声明固定书类下载。
        GET /api/subcontracting/me 返回当前三方公司信息。
        GET /api/approvals 查询独立审批模块，GET /api/approvals/pending-count 查询待处理审批数量，POST /api/approvals/{workflow_id}/decision 审批通过或拒绝，POST /api/approvals/{workflow_id}/withdraw 将已通过审批撤回到 pending。当前 workflow_type=partner_quotation/reimbursement；admin/hr 可看全部，pm 仅看与自己相关的契约审批，pm 不处理报销审批。
    8.报销管理
        GET/POST/PUT/DELETE /api/reimbursements 管理报销记录；POST 支持多文件上传发票/凭证。普通员工和 pm 只能管理自己的 pending/rejected 记录，admin/hr 可管理全部；approved 记录锁定，不允许普通编辑或删除。
        GET /api/reimbursements/{reimbursement_id}/files/{index}/download 下载报销凭证。报销提交后自动进入 workflow_requests，承认后按报销支给月份反映到工资；若该月工资已锁定则只记录提醒，不自动改工资。

数据库设计文档
    设计原则
        1.保持影响最小：每个业务模块控制在1-2张核心表，跨模块需要逻辑关系时才建立外键。
        2.人员是业务主数据，契约、工资、案件归属均通过 employee_id 关联 employees。
        3.解析型、AI型、PDF型非固定字段统一放在 JSON attributes 或原文 text 中，避免频繁改表。

    1.基础认证/人员模块
        employees：人员主数据表。
            id PK；code；full_name；name_kana；birth_date；graduation_status；residence；nearest_station；email；phone；age；languages；certifications；technical_experience；it_years；talent_category；skills JSON；nationality；employee_type；estimated_annual_salary；estimated_annual_salary_manual；is_deleted；deleted_at；created_at；updated_at。
            唯一约束：full_name + email，避免同一姓名同一邮箱重复收录；历史 email unique 仍兼容已存在数据。
            employee_type 选项：一般社員、hr、営業、管理者。为空时按一般社員处理。该字段为人员属性；自动创建的平台登录账号默认权限仍为一般员工。estimated_annual_salary 默认由“有项目归属时的月工资 * 12”计算，HR/admin 手动修改后 estimated_annual_salary_manual=true，后续自动计算不覆盖。is_deleted=true 表示人员被逻辑删除，deleted_at 记录删除时间；业务列表、工资批量、案件推荐和新增关联默认过滤已删除人员。
        users：登录用户表。
            id PK；email unique；login_id unique；full_name；role(admin/hr/pm/employee/partner)；password_hash；is_active；must_reset_password；employee_id FK -> employees.id；partner_id FK -> business_partners.id；created_at。
            说明：内部用户可用 email 登录，新员工账号由 employees.full_name 生成，格式为 姓拼音_名拼音@nit-g.co.jp；三方用户用 login_id 登录，格式 NIT_PARTNER_公司名或公司假名发音，通过 partner_id 绑定 business_partners；admin/hr/pm/partner 通过 role 控制页面和接口权限。admin 在人员管理修改 employees.employee_type 时同步更新 users.role，并可在人员管理重置员工密码。员工逻辑删除时保留 user.employee_id 但将 is_active=false，恢复人员时复用原账号。must_reset_password=true 时只能访问改密和退出接口。
        password_reset_tokens：密码重置令牌表。
            id PK；user_id FK -> users.id；token_hash unique；expires_at；used_at；created_at。

    2.契约/工资模块
        contracts：契约主表。
            id PK；employee_id FK -> employees.id；title；contract_type；vendor_company；start_date；end_date；pdf_filename；parsed_text；attributes JSON；created_at；updated_at。
            说明：PDF 解析得到的基本工资、手当、业务内容、工作地点等放在 attributes；长期契约 end_date 使用 9999-12-31。
        salary_records：月度工资表。
            id PK；employee_id FK -> employees.id；year_month(YYYY-MM)；estimated_salary；actual_salary；reimbursement_amount；locked；note；source；created_at；updated_at。
            唯一约束：employee_id + year_month。
            说明：默认预计工资由当前契约 attributes.base_salary 计算；有项目归属时加 attributes.allowance_total，无项目归属时只取基本工资。审批通过且支给月份匹配的报销金额计入 reimbursement_amount 并加到 actual_salary 默认值。HR/admin 可更新 actual_salary，homepage 实时读取该月记录；月度结算工资支出按 actual_salary 汇总。locked=true 后工资不再被项目归属、报销审批撤回等联动自动覆盖，涉及钱的修改需先解锁。

    3.案件模块
        projects：案件主表。
            id PK；client_company；project_name；description；required_skills JSON；workplace；nationality_requirement；duration；start_date；end_date；headcount；unit_price；source_email_subject；raw_email；attachment_name；attributes JSON；created_at；updated_at。
            说明：AI 解析结果中的 remote_type、station、source_confidence、fallback_fields 等放在 attributes；headcount 同时是展示字段和归属人数上限。
        project_assignments：案件人员归属表。
            id PK；project_id FK -> projects.id；employee_id FK -> employees.id；role；status；created_at。
            说明：status=assigned 计入项目归属人数；新增归属时若已达到 projects.headcount 则拒绝。

    4.邮箱/系统设置模块
        mail_settings：邮箱配置表。
            id PK；provider；enabled；imap_enabled；imap_host；imap_port；imap_username；imap_password_encrypted；imap_folder；poll_interval_seconds；smtp_enabled；smtp_host；smtp_port；smtp_username；smtp_password_encrypted；smtp_from；smtp_use_tls；created_at；updated_at。
            说明：IMAP 用于案件邮件监听，SMTP 用于通知和密码重置，密码字段仅保存加密值。

    5.v0.7 内部契约/工资扩展
        salary_records：月度工资表，在原有表上扩展。
            新增字段：monthly_hours；payable_salary；calculation_detail JSON。
            唯一约束：employee_id + year_month。
            说明：monthly_hours 为空时，计算支给额按基本工资计算；monthly_hours 有值时，计算支给额按基本工资 + 手当合计进入工时段计算。工时段、年金、住民税、保险费用、动态基本单价放在 calculation_detail JSON，不新增物理列，默认工时段为 140-180。
            公式：设工时段为 low-high，则基本单价低 = 基本工资 / high，基本单价高 = 基本工资 / low；小于 low 小时，计算支给额 - 基本单价高 * (low - monthly_hours)；low 到 high 小时，正常工资；大于 high 小时，计算支给额 + 基本单价低 * (monthly_hours - high)。
            actual_salary 默认值 = 计算支给额 - (年金 + 住民税 + 保险费用)，仍可由 HR/admin 手动调整；monthly_settlements 的工资支出只按 actual_salary 扣减。payable_salary 为兼容历史字段，前端不再展示或编辑。

    6.v0.7 外部契约模块
        business_partners：已缔结公司/取引先主表。
            id PK；company_name unique；partner_type(upstream/downstream/both)；contracted_at；status；contact_name；email；phone；address；bank_info JSON；note；attributes JSON；created_at；updated_at。
            说明：上家、下家、两者兼具都放在同一张表，发注书、请求书、契约记录均通过 partner_id 关联；相关人员暂存在 attributes.related_people，公司假名暂存在 attributes.company_kana。契约结束时间暂存在 attributes.contract_end_date，已经解约暂存在 attributes.terminated。公司是否仍为有效契约公司由 status=active、未解约、且 contract_end_date 为空或大于等于当天共同决定；任一条件不满足即视为失效。admin 可逻辑删除公司，删除时 status=deleted 且 attributes.deleted=true。

        external_contracts：外部契约记录表。
            id PK；partner_id FK -> business_partners.id；direction(upstream/downstream/both)；title；contract_type；status；contracted_at；download_token；file_paths JSON；note；attributes JSON；created_at；updated_at。
            说明：新缔结契约由前端输入公司名，不从已缔结公司下拉选择。前端将“状态”和“缔结成功”合并为一个缔结成功开关，提交时自动派生 status=draft/signed，后端仍保留 status 字段兼容历史数据。默认缔结成功为否，此时公司状态为 pending，不出现在已缔结公司列表；缔结成功为是或契约状态为 signed 时，公司状态置为 active 并进入已缔结公司列表，同时清空该公司的解约/结束日期。admin/营业可修改契约方向、缔结状态、删除契约记录。契约到期不放在 external_contracts，统一由 business_partners 的契约结束时间和已经解约控制；同名公司若仍为有效契约公司，则不能再次新缔结契约，失效后才可重新缔结。下家或 both 新缔结契约会生成 download_token，用于 NIT-1 到 NIT-5 固定文件的 demo 下载 link；上家契约可多文件上传并留痕，上传时可选择失效的已缔结公司，也可手输新公司并自动建立取引先；上传文件路径保存在 file_paths，可在后台 UI 下载。

        external_documents：外部书类表。
            id PK；partner_id FK -> business_partners.id；external_contract_id FK -> external_contracts.id；source_document_id FK -> external_documents.id；document_type(purchase_order/quotation/invoice/uploaded_contract/partner_quotation)；direction；document_no；target_month；issue_date；due_date；subtotal；tax；total；items JSON；file_path；note；attributes JSON；created_by FK -> users.id；created_at；updated_at。
            说明：发注书、見積書、请求书、上传契约、三方提交的見積書统一记录。downstream 公司只能生成发注书，upstream 公司只能生成見積書和请求书，both 公司三类书都可生成。三方 partner_quotation 由准委任模块上传原始文件，文件路径保存到 file_path，审批下载即下载该上传文件；审批状态放在 attributes.approval_status，审批通过后才能作为 source_document_id 生成 purchase_order，审批撤回时复位为 pending。请求书可由見積書生成，通过 source_document_id 关联。target_month 作为月度归集字段，不按实际发行日归集。结算状态放在 attributes.settlement：confirmed 表示是否实收/实付，actual_amount 表示实收/实付金额；默认 confirmed=true，actual_amount=total。逻辑删除放在 attributes.deleted，列表和月度结算默认过滤 deleted=true 的记录。

    7.v0.8 准委任/外部人员/审批模块
        workflow_requests：通用审批流表。
            id PK；workflow_type；entity_type；entity_id；title；status(pending/approved/rejected)；requester_id FK -> users.id；approver_id FK -> users.id；submitted_at；decided_at；comment；attributes JSON；created_at；updated_at。
            说明：当前用于三方 partner_quotation 审批和报销 reimbursement 审批。partner_quotation 的 entity_type=external_document，entity_id 指向 external_documents.id；审批通过时同步写回 external_documents.attributes.approval_status=approved，撤回时 workflow_requests.status 和 external_documents.attributes.approval_status 均复位为 pending。reimbursement 的 entity_type=reimbursement，entity_id 指向 reimbursements.id；审批通过/撤回时同步报销状态，并在工资未锁定时重新计算对应支给月份工资。后续 HR 离职、在留资格等流程可复用该表。

        external_personnel：外部入场人员表。
            id PK；partner_id FK -> business_partners.id；full_name；company_name；assignment_month(YYYY-MM)；contract_end_date；monthly_hours；resume_path；avatar_path；timesheet_path；status(submitted/confirmed/rejected/deleted)；note；attributes JSON；created_by FK -> users.id；confirmed_by FK -> users.id；confirmed_at；created_at；updated_at。
            说明：三方在准委任模块提交入场人员后自动创建记录；三方只能查看自己的人员，admin/hr 可查看、修改、确认、拒绝、删除。三方提交人员前必须存在同一 partner_id + assignment_month 的已审批 partner_quotation；CV 和 PNG 头像为必填，工时表可选。文件 demo 存本地，DB 保存路径；上线可替换为 S3。

        monthly_settlements：月度结算表。
            id PK；year_month unique；invoice_total；purchase_order_total；salary_total；net_income；detail JSON；locked；created_at；updated_at。
            说明：按 target_month 汇总请求书收入、发注书支出、工资支出；请求书收入和发注书支出按 external_documents.attributes.settlement 中的实收/实付金额计算，未确认时计入 0；工资支出按 salary_records.actual_salary 汇总，net_income = invoice_total - purchase_order_total - salary_total。detail JSON 保存当月请求书和发注书明细快照。

        audit_logs：API 修改审计日志表。
            id PK；user_id FK -> users.id；user_email；method；path；module；action；entity_type；entity_id；before JSON；after JSON；ip；created_at。
            说明：记录成功的非 GET API 调用，由谁在什么时间修改过什么值；password、token、api_key 等敏感字段脱敏；不在前端展示。

    8.v0.9 报销/首页/日文数据规范
        reimbursements：报销记录表。
            id PK；expense_type；period_start_month；period_end_month；employee_id FK -> employees.id；amount；pay_month；status(pending/approved/rejected/deleted)；invoice_file_paths JSON；note；requester_id FK -> users.id；approver_id FK -> users.id；approved_at；attributes JSON；created_at；updated_at。
            说明：expense_type 选项为 交通費、出張費、懇親会費、その他。period_start_month 到 period_end_month 表示报销发生期间，amount 为总金额，pay_month 默认申请承认的下个月。发票/凭证支持多文件，本地 demo 保存路径在 invoice_file_paths，上线可替换为 S3。approved 后锁定业务编辑，撤回审批后状态回 pending。承认后进入对应 pay_month 工资，工资 locked 时不自动覆盖并给出提醒。

        数据字符集与业务值：
            MySQL 初始化/启动时按 utf8mb4 / utf8mb4_unicode_ci 处理，支持日文汉字、假名和英文。前端保留 ja/zh/en 国际化，但数据库业务枚举尽量存日文值：国籍为 中国/日本/その他，毕业状态为 大学卒業/短大卒業/大学院修了/中退・その他，契约类型为 正社員/契約社員/freelance/アルバイト/その他，案件国籍要求为 日本籍のみ/制限なし。

        首页与下载：
            内部员工首页展示个人信息、当前契约、当前项目、当月工资和想定年収；工资卡可进入明细，按年月查看，并下载工资明细 PDF 和想定年収 PDF。三方 partner 首页只展示准委任入口、三方公司信息和 NIT 静态会社介绍，不展示内部员工工资/契约。

        前端模块调整：
            外部契约管理内的审批/申请子界面摘除，审批变为独立模块；独立审批模块分为契约审批和报销审批。报销模块对三方不可见，admin/hr 可管理全部，pm/一般社員只处理自己的记录。普通员工不可见案件管理。

部署设计文档
    1.生产容器拓扑
        docker-compose.prod.yml：包含 mysql、redis、backend、frontend 四个服务。
        frontend：多阶段构建 Vue 静态文件，最终由 nginx:1.27-alpine 提供页面，并将 /api、/docs、/openapi.json 反向代理到 backend:8000。
        backend：python:3.12-slim + FastAPI/Uvicorn，容器内监听 0.0.0.0:8000，只在 compose 内部网络暴露给 nginx。
        mysql/redis：均使用官方镜像，生产 compose 默认不向宿主机暴露数据库和 Redis 端口；数据目录分别挂载到 /opt/nit-ao/mysql 与 /opt/nit-ao/redis。
    2.跨域策略
        前端 axios baseURL 使用相对路径 /api；生产环境浏览器只访问 nginx 同源地址，因此正常业务流不触发跨域。
        FastAPI 保留 BACKEND_CORS_ORIGINS，用于直连 API 或调试场景；正式域名需写入 .env。
    3.持久化
        /opt/nit-ao/config/app.env：运行时环境变量配置，修改后重启容器即可生效，不需要重新构建镜像。
        /opt/nit-ao/mysql：MySQL 数据。
        /opt/nit-ao/redis：Redis AOF 数据。
        /opt/nit-ao/storage：上传文件、生成书类、导入输出等后端存储。
        /opt/nit-ao/refer：固定书类模板，以只读方式挂载到 /app/refer。
    4.镜像与配置
        backend/Dockerfile 构建 japan-nit-oa-backend:${APP_VERSION:-0.8}。
        frontend/Dockerfile 构建 japan-nit-oa-frontend:${APP_VERSION:-0.8}。
        .env.production.example 提供 /opt/nit-ao/config/app.env 的模板；DEPLOY.md 记录构建、启动、升级、ECR 镜像部署和停止命令。
v0.9 fix 追加设计文档

1.准委任会社通知
    partner_onboarding_items：三方会社通知/必要书类完成状态表。
        id PK；partner_id FK -> business_partners.id；item_code(nit-1/nit-2/nit-3/nit-4/nit-5)；status(pending/completed)；form_data JSON；file_path；original_filename；completed_at；updated_by FK -> users.id；created_at；updated_at。
        说明：NIT-1、NIT-2、NIT-5 使用页面弹窗阅读和结构化填写，必须滚动到底部并填完必填项后才能 completed。NIT-3、NIT-4 为模板下载后上传完成版，上传成功后 completed。partner 提交三方見積書前，后端检查五项均 completed，否则拒绝提交。

2.三方书类闭环
    external_documents.document_type 新增 partner_invoice。
        partner_quotation：三方上传見積書，target_month 保存对象开始月，attributes.target_start_month/target_end_month 保存对象区间，审批状态保存到 attributes.approval_status。
        purchase_order：NIT 基于 approved partner_quotation 生成的发注书，source_document_id 指向 partner_quotation。
        partner_invoice：三方基于 approved partner_quotation 上传请求书，source_document_id 指向 partner_quotation；target_month 保存希望支払月；total 使用页面手动录入金额，上传原始请求书保存到 file_path；审批状态保存到 attributes.approval_status。
        闭环规则：一组正常请款链路应包含 approved partner_quotation、purchase_order、approved partner_invoice。外部契约管理页面对缺少发注书或 approved partner_invoice 的 approved partner_quotation 显示提醒。

3.月次精算
    monthly_settlements 仍保持原表结构。
        收入 invoice_total：按 NIT 向上家生成的 invoice 汇总。
        支出 purchase_order_total：v0.9 起按 approved partner_invoice 汇总，不再按 purchase_order 汇总；字段名保持 purchase_order_total 以减少接口影响，前端显示为三方请求书/パートナー請求書合计。
        工资 salary_total：按 salary_records.actual_salary 汇总。审批撤回 partner_invoice 后，下次读取月次精算会立刻从支出中扣除；已 locked 的月次精算不自动重算。

4.工资自动重算
    salary_records 新增响应字段 actual_salary_manual，表示 actual_salary 与 calculation_detail.actual_salary_default 不一致。
        未 locked 的工资单：契约金额、项目归属、扣除项、报销承认/撤回等变化触发默认值重算。
        已 locked 的工资单：不自动重算。
        手动改过 actual_salary 的未锁定工资单：不覆盖实发值，前端标红提示“手動調整あり”。

5.勤怠管理
    attendance_settings：勤怠全局设置表。
        id PK；default_start_time；default_end_time；break_minutes；hour_step；default_paid_leave_days；paid_leave_counts_as_work；leave_policies JSON；company_holidays JSON；created_at；updated_at。
        说明：默认勤務为 09:00-18:00，休憩 60 分，給与反映工数为 8h；工数丸め默认 0.5h。有給默认 10 天。paid_leave_counts_as_work 默认 false，表示有給休暇不计入給与月間工数；如公司制度确定按出勤计，可由 admin 打开。

    work_calendar_days：勤務日历表。
        id PK；work_date unique；is_workday；holiday_name；source(system/company/manual)；note；created_at；updated_at。
        说明：可导入日本祝日和公司休日，未请假/未调整的勤務日默认按 settings 计算工时。manual 修改不会被再次导入覆盖。calendar 变化会触发未 locked 工资重算。

    attendance_requests：勤怠申請/調整表。
        id PK；employee_id FK -> employees.id；work_date；request_type(paid_leave/absence/morning_off/afternoon_off/special_leave/holiday_work/adjustment)；requested_hours；status(pending/approved/rejected)；reason；requester_id FK -> users.id；approver_id FK -> users.id；approved_at；attributes JSON；created_at；updated_at。
        说明：一般社員/pm 可提交自己的勤怠申請；admin/hr 可代录且默认 approved。approved 后进入月間工数计算，并刷新对应月份未 locked 的 salary_records.monthly_hours 与工资默认值；approved 可撤回为 pending。

    attendance_leave_balances：年休残数表。
        id PK；employee_id FK -> employees.id；fiscal_year；granted_days；adjustment_days；note；created_at；updated_at。
        唯一约束：employee_id + fiscal_year。
        说明：默认 granted_days 取 attendance_settings.default_paid_leave_days；admin/hr 可手动调整 granted_days 和 adjustment_days。审批 paid_leave/morning_off/afternoon_off 时检查剩余天数。

    工资联动：
        salary_records.monthly_hours 不再由前端手动编辑，来源为勤怠月間工数。有项目归属时按月間工数、工时段、基本給、手当、扣除项和已承认报销计算；无项目归属时仍只按基本給计算，月間工数仅展示和留痕。locked=true 的工资单不被勤怠、项目、报销等联动自动覆盖。

v0.9 給与・書類管理 追記

1. 給与計算
    salary_records の物理列は増やさず、支給・控除の計算結果を calculation_detail JSON に保持する。
    calculation_detail.payment_items に支給明細を保持する。主な項目は 基本給、手当合計、時間外手当、不就労控除、通勤手当（非課税）、経費精算、その他支給。
    calculation_detail.deduction_items に控除明細を保持する。主な項目は 健康保険、介護保険、厚生年金、雇用保険、所得税、住民税、その他控除。
    既存 insurance_fee は health_insurance として互換処理する。UI 表示は健康保険に寄せる。
    雇用保険と所得税は v0.9 では概算自動計算を行い、HR/admin が手動修正できる。手動修正後の値は calculation_detail に保存される。
    actual_salary_default = gross_payment_total - deduction_total。gross_payment_total には計算支給額、通勤手当、承認済み経費精算、その他支給を含む。課税支給額は通勤手当と経費精算を除外する。
    給与明細 PDF は全日文で、勤怠、支給、控除、総支給額、控除合計、差引支給額を表示する。

2. 外部契約 UI
    外部契約管理の表示順は 新規契約締結、締結済み会社、発注書作成、見積書作成、請求書作成、書類履歴、月次精算 とする。
    書類作成は発注書、見積書、請求書を独立した UI に分離する。発注書は承認済みパートナー見積書を必須とし、見積書/請求書は upstream または both の会社を対象とする。

3. 書類管理
    document_archives：書類归档索引表。
        id PK；source_key unique；source；source_id；document_type；name；storage_path；directory_path；owner_name；partner_name；employee_name；target_month；status；amount；hidden；missing；attributes JSON；created_at；updated_at。
        说明：全書類管理通过 document_archives 做统一索引。GET /api/documents 时会同步 external_documents、reimbursements.invoice_file_paths、partner_onboarding_items、external_personnel 的文件记录；同时扫描 backend/storage 下 external_documents、external_uploads、external_personnel、reimbursements、subcontracting 目录，把没有业务表映射的历史文件以 storage_scan 来源补录进归档表。
        新生成/上传的书类：只要业务表保存 file_path，下一次进入全書類管理时会自动 upsert 到 document_archives。
        历史文件：如果没有业务表记录，也会按本地目录扫描补录，document_type 由文件名和目录推断，source 显示为 履歴ファイル。
        下载：全書類管理统一使用 /api/documents/archive/{archive_id}/download，由归档表 storage_path 映射到本地文件；上线 S3 时可把该下载层替换为 S3 signed URL。
        删除：全書類管理删除为逻辑隐藏。归档表 hidden=true 是第一层控制；有业务来源的记录还会同步写回原业务表 attributes/form_data 的 hidden_document_keys 或 deleted 作为第二层控制，避免业务模块重新同步时又显示出来。
    管理対象は外部契約書類、三方見積書/請求書、会社通知アップロード、報销証憑、外部人員の履歴書・顔写真・勤務表，以及本地 storage 中可识别的历史文件。

v0.9 UI 導線・権限管理 追記

1. 左メニュー再編
    契約管理：
        内部契約管理、新規契約締結、締結済み会社。
        外部契約管理から書類作成、書類履歴、月次精算を分離する。

    書類管理：
        発注書作成、見積書作成、請求書作成、書類履歴、全書類管理。
        発注書/見積書/請求書作成は既存 external_documents 系 API を利用し、書類履歴は外部契約書類の履歴を表示する。全書類管理は /api/documents で集約した全ファイルを admin が管理する。

    経費・精算：
        経費申請、月次精算。
        月次精算は既存 /api/external/settlements/{year_month} を利用し、UI 上は契約管理から分離する。

    承認：
        契約承認、経費承認、勤怠承認。
        勤怠承認は勤怠管理から移動し、承認 UI の単一入口で処理する。勤怠申請一覧では承認/却下ボタンを表示しない。

    勤怠管理：
        勤怠一覧、勤怠申請、カレンダー設定。

2. ui_role_permissions：前端メニュー/ルート表示権限表。
    id PK；role unique；route_keys JSON；updated_by FK -> users.id；created_at；updated_at。
    説明：この表は前端のメニューとルート表示のみを制御する。API の実操作権限は既存 MODULE_PERMISSIONS と各 router の ensure_role/ensure_permission で保護する。admin は安全のため常に全 UI route を持ち、権限管理画面から削除できない。

    初期 route key：
        home。
        employees.internal / employees.external。
        contracts.internal / contracts.external.new / contracts.external.partners。
        documents.purchase_orders / documents.quotations / documents.invoices / documents.history / documents.library。
        approvals.contracts / approvals.reimbursements / approvals.attendance。
        reimbursements.claims / reimbursements.monthly_settlement。
        subcontracting.notice / subcontracting.quotations / subcontracting.invoices / subcontracting.personnel。
        attendance.summary / attendance.requests / attendance.settings。
        projects / settings.mail / settings.permissions。
