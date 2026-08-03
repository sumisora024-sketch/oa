export default {
  app: { title: 'NIT OA system', logout: '退出', language: '语言', role: '角色', changePassword: '修改密码' },
  nav: { home: '首页', employees: '人员管理', internalEmployees: '内部人员管理', externalEmployees: '外部人员管理', contracts: '契约管理', internalContracts: '内部契约管理', externalContracts: '外部契约管理', externalContractsNew: '新缔结契约', externalPartners: '已缔结公司', documentManagement: '书类管理', purchaseOrders: '生成发注书', quotations: '生成見積書', invoices: '生成请求书', documentHistory: '书类履历', documentLibrary: '全书类管理', approvals: '审批', contractApprovals: '契约审批', reimbursementApprovals: '报销审批', reimbursements: '报销管理', expenseSettlement: '经费・精算', reimbursementClaims: '报销申请', salaryDetails: '工资明细', monthlySettlement: '月次精算', subcontracting: '准委任', subcontractingNotice: '公司通知', subcontractingQuotations: '三方見積書', subcontractingInvoices: '三方请求书', subcontractingPersonnel: '入场人员', attendance: '勤怠管理', attendanceSummary: '勤怠一览', attendanceRequests: '勤怠申请', attendanceApprovals: '勤怠审批', attendanceSettings: '日历设置', projects: '案件管理', settings: '系统设置', mailSettings: '邮箱配置', permissionManagement: '权限管理' },
  login: { title: '登录', email: '邮箱', password: '密码', submit: '登录', forgot: '重置密码', sso: 'Teams SSO', eyebrow: 'NIT DX Portal', headline: '让工作更轻松。', headlineAccent: 'NIT OA system', subhead: '把人员、契约与案件连接在一起，减少查找和确认的时间。', panelEyebrow: 'Staff entrance', panelHint: '必要信息集中在这里，进入后即可处理日常工作。', capabilities: { people: '人员信息可视化', contracts: '契约与工资快速确认', projects: '案件归属更顺畅' }, forceResetTitle: '首次登录重置密码', forceResetHint: '系统检测到你正在使用初始密码，请先设置新密码。', changePasswordTitle: '修改密码', changePasswordHint: '请输入当前密码并设置新密码。', currentPassword: '当前密码', newPassword: '新密码', confirmPassword: '确认新密码' },
  common: { search: '搜索', create: '新建', edit: '编辑', delete: '删除', save: '保存', cancel: '取消', import: '导入', upload: '上传', download: '下载', actions: '操作', refresh: '刷新', analyze: '分析', recommend: '推荐', assign: '分配', send: '发送', required: '必填', success: '成功', failed: '失败', columns: '显示列', detail: '详情', yes: '是', no: '否', confirmDelete: '确认删除这条记录吗？' },
  validation: { required: '此项为必填', email: '请输入有效邮箱', employeeName: '姓名只能包含日文、汉字或英文', jpPhone: '请输入符合日本地区规则的电话', passwordMismatch: '两次输入的新密码不一致' },
  fields: {
    id: 'ID', fullName: '姓名', nameKana: '日文假名', email: '邮箱', platformEmail: '平台账号', phone: '电话', birthDate: '出生年月日', age: '年龄', graduationStatus: '毕业状态', residence: '居住地', nearestStation: '最近车站', nationality: '国籍', employeeType: '员工类型', languages: '语言能力', certifications: '证书', technicalExperience: '技术经历', itYears: 'IT工龄', talentCategory: '人才分类', skills: '技术栈',
    title: '标题', employee: '人员', contractType: '契约类型', vendorCompany: '契约公司', startDate: '开始日', endDate: '结束日',
    baseSalary: '基本工资', allowanceTotal: '手当合计', baseUnitPriceLow: '基本单价低', baseUnitPriceHigh: '基本单价高', salaryTotalMonthly: '月额合计', duty: '业务内容',
    allowances: '手当明细', amount: '金额', pdfFile: 'PDF 文件', parsedText: '解析文本', yearMonth: '年月', hoursRange: '工时段', monthlyHours: '月度工时', estimatedSalary: '计算支给额', payableSalary: '应给工资', actualSalary: '当月支给工资', reimbursementAmount: '経費精算', grossPaymentTotal: '总支给额', deductionTotal: '控除合计', taxablePaymentTotal: '课税支给额', socialInsuranceTotal: '社会保险合计', estimatedAnnualSalary: '预估年薪', locked: '锁定', pension: '年金', residentTax: '住民税', insuranceFee: '保险费用', note: '备注',
    clientCompany: '甲方公司名', projectName: '案件项目名', description: '案件描述', requiredSkills: '所需技术栈', workplace: '工作场所', nationalityRequirement: '国籍要求', duration: '项目时长', headcount: '所需人数', assignedEmployees: '归属人员', unitPrice: '单价', createdAt: '创建时间', subject: '邮件标题', body: '邮件内容', attachmentText: '附件文本',
    source: '来源', confidence: '置信度', remoteType: '在宅类型', station: '车站', aiError: 'AI 错误', rawEmail: '原始邮件', attributes: '解析属性'
  },
  home: { profile: '个人信息', contracts: '契约信息', salary: '工资', projects: '所在案件', noData: '暂无数据', contactAdmin: '元数据不足，请联系管理员', welcome: '欢迎，', heroCopy: '今天的契约、工资和案件状态都汇集在这里。', partnerHero: '面向合作伙伴的准委任入口，资料提交、人员入场和书类下载都可以在这里完成。', salaryDetail: '工资明细', salarySummary: '工资汇总', paymentItems: '支给', deductionItems: '控除', salaryCalculationNote: '工资由勤怠、案件归属、已审批报销和控除设置自动计算。已锁定月份不会自动重算。', downloadPayslip: '下载工资单', downloadAnnual: '下载年薪PDF', assistantGreeting: '可以询问公司信息和手续流程。', assistantOnline: '在线', assistantOffline: '未配置', assistantOfflineHint: 'AI 问答助手尚未配置，请管理员设置 Dify API Base 和 API Key。', assistantError: 'AI 问答助手发生错误。', assistantPlaceholder: '输入问题', assistantNewChat: '新会话', assistantSources: '参考来源', assistantSuggestionPeople: '请说明入职和退职手续', assistantSuggestionExpense: '请说明报销申请流程', assistantSuggestionContract: '请说明契约书类提交方法' },
  employees: { importHelp: '支持普通表格和技術者経歴書固定格式', employmentInfo: '在职信息', defaultPassword: "新员工平台账号按 姓拼音_名拼音{'@'}nit-g.co.jp 生成，默认密码来自 DEFAULT_EMPLOYEE_PASSWORD，首次登录必须重置密码", resetPassword: '重置密码', resetPasswordConfirm: '确认将 {name} 的密码重置为默认密码吗？', passwordResetDone: '密码已重置: {email}' },
  contracts: { importPdf: '导入 PDF 契约', due: '30日内到期', sendReminders: '发送到期提醒', longTerm: '长期', batchNote: '到期提醒由每日 09:00 batch 自动发送，收件人来自 HR_REMINDER_EMAIL。', detailTitle: '契约详情', salaryDetail: '工资与单价', contractInfo: '契约信息', salaryManagement: '工资明细' },
  external: {
    partners: '已缔结公司', contracts: '新缔结契约', documents: '书类生成', approvals: '审批', settlement: '月度结算',
    newPartner: '新增公司', newContract: '新缔结契约', uploadUpstream: '上传上家契约', companyName: '公司名', companyKana: '公司假名', partnerType: '方向', partnerAccount: '三方账号', temporaryPassword: '临时密码', sendPartnerAccount: '发送账号密码', sendPartnerAccountConfirm: '将重置临时密码并发送到联系人邮箱，确认发送吗？', accountMailSent: '账号密码邮件已发送', accountMailMissingEmail: '请先填写联系人邮箱',
    contractedAt: '缔结时间', contractedSuccess: '缔结成功', contractEndDate: '契约结束时间', terminated: '已经解约', contractActive: '契约生效', contactName: '联系人', relatedPeople: '相关人员', address: '地址', direction: '上下家', status: '状态', fixedFiles: '固定文件', downloadFixedPack: '下载固定文件包', useExistingCompany: '选择已缔结公司',
    generateDocuments: '生成发注书 / 見積書', generatePurchaseOrder: '生成发注书', generateQuotation: '生成見積書', invoiceFromQuotation: '由見積書生成请求书',
    selectQuotation: '选择見積書', approvedQuotation: '已审批三方見積書', approvedQuotationRequired: '请先选择已审批三方見積書', generateInvoice: '生成请求书', targetMonth: '対象年月', issueDate: '发行日', dueDate: '支付期限',
    itemName: '项目', quantity: '数量', unitPrice: '单价', baseHours: '基本时间幅', documentType: '书类类型', documentNo: '书类编号',
    total: '合计金额', invoiceTotal: '请求书合计', purchaseTotal: '三方请求书合计', salaryTotal: '实发工资合计', netIncome: '本月支入支出',
    downstreamOnly: '发注书只能用于 downstream 或 both 公司',
    upstreamOnly: '見積書和请求书只能用于 upstream 或 both 公司',
    documentRuleHint: '书类方向：downstream 只能做发注书；upstream 能做見積書和请求书；both 都可以。',
    invoiceDetails: '请求书收入明细', purchaseDetails: '三方请求书支出明细', received: '是否实收', receivedAmount: '实收金额', paid: '是否实付', paidAmount: '实付金额', effectiveAmount: '计入金额',
    pendingApprovals: '待处理审批', approvalStatus: '审批状态', approve: '通过', reject: '拒绝', withdraw: '撤回',
    documentTypes: { purchase_order: '发注书', quotation: '見積書', invoice: '请求书', uploaded_contract: '上传契约', partner_quotation: '三方見積書', partner_invoice: '三方请求书' }
  },
  subcontracting: { partnerQuotation: '三方見積書', submitQuotation: '上传見積書', quotationFile: '見積書文件', approvalStatus: '审批状态', entryPersonnel: '入场人员', assignmentMonth: '委派月份', submitPersonnel: '提交人员', companyNotice: '公司须知/声明' },
  reimbursements: { expenseType: '报销项目', period: '报销月度', periodStart: '开始月份', periodEnd: '结束月份', payMonth: '报销支给月份', files: '发票/凭证', traffic: '车费', businessTrip: '出差费', teamBuilding: '团建费', other: '其他' },
  approvals: { contractApprovals: '契约审批', reimbursementApprovals: '报销审批', attendanceApprovals: '勤怠审批' },
  permissions: { hint: '此设置只控制前端菜单和路由显示，后端 API 权限仍由现有角色权限保护。', role: '目标角色' },
  projects: { analyzeEmail: '邮件拆解为案件', pollMailbox: '读取邮箱', recommendations: '候选人推荐', reasons: '理由', score: '分数', detailTitle: '案件详情', aiResult: 'AI 解析结果', assignmentFull: '已达到项目所需人数，不能继续归属', reassign: '重新归属', unassign: '撤回归属', unassignConfirm: '确认撤回该人员的项目归属吗？' }
  ,
  settings: {
    mail: '邮箱配置', provider: '方案', disabled: '关闭', gmail: 'Gmail App Password', generic: '通用 IMAP+SMTP', smtpOnly: '仅 SMTP',
    enabled: '启用', imapEnabled: '启用收信', smtpEnabled: '启用发信', imapHost: 'IMAP 主机', imapPort: 'IMAP 端口', imapUsername: 'IMAP 账号', imapPassword: 'IMAP 密码', imapFolder: '邮箱目录',
    smtpHost: 'SMTP 主机', smtpPort: 'SMTP 端口', smtpUsername: 'SMTP 账号', smtpPassword: 'SMTP 密码', smtpFrom: '发信人', smtpTls: 'STARTTLS', pollInterval: '监听间隔秒数',
    hasPassword: '已保存密码', testImap: '测试收信', testSmtp: '测试发信'
  }
}
