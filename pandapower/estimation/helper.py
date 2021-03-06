from pandas import DataFrame, notnull, isnull
from pandapower.topology import create_nxgraph, connected_component


def estimate_voltage_vector(net):
    """
    Function initializes the voltage vector of net with a rough estimation. All buses are set to the
    slack bus voltage. Transformer differences in magnitude and phase shifting are accounted for.
    :param net: pandapower network
    :return: pandas dataframe with estimated vm_pu and va_degree
    """
    res_bus = DataFrame(index=net.bus.index, columns=["vm_pu", "va_degree"])
    net_graph = create_nxgraph(net, include_trafos=False)
    for _, ext_grid in net.ext_grid.iterrows():
        area = list(connected_component(net_graph, ext_grid.bus))
        res_bus.vm_pu.loc[area] = ext_grid.vm_pu
        res_bus.va_degree.loc[area] = ext_grid.va_degree
    trafos = net.trafo[net.trafo.in_service == 1]
    trafo_index = trafos.index.tolist()
    while len(trafo_index):
        for tix in trafo_index:
            trafo = trafos.loc[tix]
            if notnull(res_bus.vm_pu.at[trafo.hv_bus]) and isnull(res_bus.vm_pu.at[trafo.lv_bus]):
                try:
                    area = list(connected_component(net_graph, trafo.lv_bus))
                    shift = trafo.shift_degree if "shift_degree" in trafo else 0
                    ratio = (trafo.vn_hv_kv / trafo.vn_lv_kv) / (net.bus.vn_kv.at[trafo.hv_bus]
                                                                 / net.bus.vn_kv.at[trafo.lv_bus])
                    res_bus.vm_pu.loc[area] = res_bus.vm_pu.at[trafo.hv_bus] * ratio
                    res_bus.va_degree.loc[area] = res_bus.va_degree.at[trafo.hv_bus] - shift
                except KeyError:
                    raise UserWarning("An out-of-service bus is connected to an in-service "
                                      "transformer. Please set the transformer out of service or"
                                      "put the bus into service. Treat results with caution!")
                trafo_index.remove(tix)
            elif notnull(res_bus.vm_pu.at[trafo.hv_bus]):
                # parallel transformer, lv buses are already set from previous transformer
                trafo_index.remove(tix)
            if len(trafo_index) == len(trafos):
                # after the initial run we could not identify any areas correctly, it's probably a transmission grid
                # with slack on the LV bus and multiple transformers/gens. do flat init and return
                res_bus.vm_pu.loc[res_bus.vm_pu.isnull()] = 1.
                res_bus.va_degree.loc[res_bus.va_degree.isnull()] = 0.
                return res_bus
    return res_bus
