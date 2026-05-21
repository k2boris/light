package com.blackbox.bian.generated;

import com.blackbox.runtime.mapping.MappingPlan;
import com.blackbox.runtime.mapping.ReverseMappingPlan;
import java.util.List;

/** Ordered registry of generated BIAN Java mappings. */
public final class BianGeneratedMappings {
    private BianGeneratedMappings() {}
    public static List<MappingPlan> forwardPlans() {
        return List.of(
                new BiSourceSystem_MdmInfaDsCXrefPartyPlan(),
                new BiParty_AmlOraDsAmlPartyPlan(),
                new BiParty_CoreTmnsDsCustomerPlan(),
                new BiParty_CrmSfDsSfPartyPersonPlan(),
                new BiParty_DowjonesDsDjEntityPlan(),
                new BiParty_MdmInfaDsCBoPartyPlan(),
                new BiPerson_AmlOraDsAmlPartyPlan(),
                new BiPerson_CrmSfDsSfPartyPersonPlan(),
                new BiPerson_DowjonesDsDjEntityPlan(),
                new BiPartyIdentifier_AmlOraDsAmlPartyPlan(),
                new BiPartyIdentifier_CrmSfDsSfIdentityDocumentPlan(),
                new BiContactPoint_CrmSfDsSfContactPointPlan(),
                new BiPostalAddress_CrmSfDsSfAddressPlan(),
                new BiSourceReference_DowjonesDsDjEntityPlan(),
                new BiSourceReference_MdmInfaDsCXrefPartyPlan(),
                new BiKycCase_AmlOraDsAmlAlertPlan(),
                new BiKycCase_CrmSfDsSfPartyPersonPlan(),
                new BiKycAssessment_AmlOraDsAmlPartyRiskPlan(),
                new BiKycAssessment_CoreTmnsDsCustomerPlan(),
                new BiKycAssessment_CrmSfDsSfKycCheckPlan(),
                new BiKycRequirementItem_CrmSfDsSfConsentPlan(),
                new BiKycRequirementItem_CrmSfDsSfIdentityDocumentPlan(),
                new BiEvidenceDocument_CrmSfDsSfConsentPlan(),
                new BiEvidenceDocument_CrmSfDsSfIdentityDocumentPlan(),
                new BiScreeningRun_AmlOraDsAmlScreeningSubjectPlan(),
                new BiScreeningRun_CoreTmnsDsPaymentScreeningPlan(),
                new BiScreeningHit_AmlOraDsAmlScreeningMatchPlan(),
                new BiScreeningHit_CoreTmnsDsPaymentScreeningPlan(),
                new BiScreeningHit_DowjonesDsDjListingPlan(),
                new BiScreeningDisposition_AmlOraDsAmlMatchDispositionPlan(),
                new BiScreeningDisposition_CoreTmnsDsPaymentScreeningPlan()
        );
    }
    public static List<ReverseMappingPlan> reversePlans() {
        return forwardPlans().stream().map(plan -> (ReverseMappingPlan) plan).toList();
    }
}
